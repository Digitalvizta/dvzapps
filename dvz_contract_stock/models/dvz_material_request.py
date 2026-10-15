from collections import defaultdict
from datetime import datetime, time

from odoo import _, api, fields, models
from odoo.exceptions import UserError, ValidationError
from odoo.tools import float_compare, float_is_zero


class DvzMaterialRequest(models.Model):
    _inherit = 'dvz.material.request'

    dvz_check_stock = fields.Boolean(compute='_compute_dvz_check_stock')
    dvz_picking_ids = fields.Many2many('stock.picking', 'dvz_material_request_picking_rel', 'request_id',
                                       'picking_id', 'Store Transfers', copy=False, readonly=True)
    dvz_picking_count = fields.Integer(compute='_compute_dvz_picking_count')

    @api.depends('company_id')
    def _compute_dvz_check_stock(self):
        for rec in self:
            company = rec.company_id or self.env.company
            rec.dvz_check_stock = company.dvz_mr_check_stock and company._dvz_feature('site_stores')

    @api.depends('dvz_picking_ids')
    def _compute_dvz_picking_count(self):
        for rec in self:
            rec.dvz_picking_count = len(rec.dvz_picking_ids)

    # ------------------------------------------------------------------
    def action_create_rfq(self):
        if len(self) == 1 and self.dvz_check_stock:
            return self.action_dvz_process()
        return super().action_create_rfq()

    def action_dvz_process(self):
        """Take what is free in the main store, buy the rest."""
        self.ensure_one()
        if self.state != 'approved':
            raise UserError(_('Approve the material request before processing it.'))
        lines = self.line_ids.filtered(lambda l: not l.purchase_line_id and not l.stock_move_id)
        if not lines:
            raise UserError(_('All materials of %s are already sent from the store or ordered.', self.name))
        company = self.company_id
        contract = self.contract_id
        site = contract._dvz_ensure_site_location()
        warehouse = company._dvz_warehouse()
        main = warehouse.lot_stock_id

        from_stock = []           # (line, qty in product unit)
        to_buy = {}               # line -> qty in the line's unit
        for line in lines:
            product = line.product_id
            line_uom = line.uom_id or product.uom_id
            take = 0.0
            if product.is_storable and line.qty_from_stock > 0:
                free = max(product.sudo().with_context(location=main.id).free_qty, 0.0)
                wanted = line_uom._compute_quantity(min(line.qty_from_stock, line.quantity), product.uom_id)
                take = min(wanted, free)
                if float_is_zero(take, precision_rounding=product.uom_id.rounding):
                    take = 0.0
            if take:
                from_stock.append((line, take))
            remaining = line.quantity - product.uom_id._compute_quantity(take, line_uom)
            if float_compare(remaining, 0.0, precision_rounding=line_uom.rounding) > 0:
                to_buy[line] = remaining

        picking = self.env['stock.picking']
        if from_stock:
            picking = self.env['stock.picking'].sudo().create({
                'picking_type_id': warehouse.int_type_id.id,
                'location_id': main.id,
                'location_dest_id': site.id,
                'origin': self.name,
                'company_id': company.id,
            })
            for line, qty in from_stock:
                move = self.env['stock.move'].sudo().create({
                    'picking_id': picking.id,
                    'product_id': line.product_id.id,
                    'product_uom_qty': qty,
                    'product_uom': line.product_id.uom_id.id,
                    'location_id': main.id,
                    'location_dest_id': site.id,
                    'company_id': company.id,
                    'origin': self.name,
                })
                line.write({'stock_move_id': move.id})
            picking.action_confirm()
            picking.action_assign()
            self.dvz_picking_ids = [(4, picking.id)]

        orders = self.env['purchase.order']
        if to_buy:
            orders = self._dvz_create_rfqs(to_buy)

        self.state = 'ordered'
        parts = []
        if picking:
            parts.append(_('store transfer %s', picking.name))
        if orders:
            parts.append(_('requests for quotation %s', ', '.join(orders.mapped('name'))))
        self.message_post(body=_('Processed: %s.', ' and '.join(parts)))
        if orders:
            return self.action_view_purchases()
        return self.action_dvz_view_pickings()

    def _dvz_create_rfqs(self, qty_by_line):
        """Same as 'Create RFQs' but only for the quantity still to buy."""
        if not self.env['purchase.order'].has_access('create'):
            raise UserError(_('Only purchase users can create requests for quotation.'))
        by_vendor = defaultdict(list)
        for line, qty in qty_by_line.items():
            vendor = self._dvz_vendor(line)
            if not vendor:
                raise UserError(_('Set a vendor on "%s" (or a vendor price on the product).', line.name))
            by_vendor[vendor].append((line, qty))
        analytic = self.contract_id.analytic_account_id
        planned = datetime.combine(self.date_required or fields.Date.context_today(self), time(12, 0))
        orders = self.env['purchase.order']
        for vendor, items in by_vendor.items():
            order = self.env['purchase.order'].with_company(self.company_id).create({
                'partner_id': vendor.id,
                'company_id': self.company_id.id,
                'origin': self.name,
                'dvz_contract_id': self.contract_id.id,
                'dvz_material_request_id': self.id,
            })
            for line, qty in items:
                vals = {
                    'order_id': order.id,
                    'product_id': line.product_id.id,
                    'name': line.name or line.product_id.display_name,
                    'product_qty': qty,
                    'date_planned': planned,
                    'dvz_contract_line_id': line.contract_line_id.id,
                    'dvz_request_line_id': line.id,
                }
                if line.uom_id:
                    vals['product_uom_id'] = line.uom_id.id
                if line.price_unit:
                    vals['price_unit'] = line.price_unit
                pol = self.env['purchase.order.line'].with_company(self.company_id).create(vals)
                if analytic:
                    pol.analytic_distribution = {str(analytic.id): 100.0}
                line.purchase_line_id = pol
            orders |= order
        return orders

    def action_dvz_view_pickings(self):
        self.ensure_one()
        action = {
            'type': 'ir.actions.act_window',
            'name': _('Store Transfers'),
            'res_model': 'stock.picking',
            'view_mode': 'list,form',
            'domain': [('id', 'in', self.dvz_picking_ids.ids)],
        }
        if len(self.dvz_picking_ids) == 1:
            action.update({'view_mode': 'form', 'res_id': self.dvz_picking_ids.id})
        return action


class DvzMaterialRequestLine(models.Model):
    _inherit = 'dvz.material.request.line'

    is_storable = fields.Boolean(related='product_id.is_storable')
    qty_free_store = fields.Float('Free in Store', digits='Product Unit', compute='_compute_qty_free_store',
                                  help='Quantity free (not reserved) in the main store, in the line unit.')
    qty_from_stock = fields.Float('From Store', digits='Product Unit', compute='_compute_qty_from_stock',
                                  store=True, readonly=False, precompute=True,
                                  help='Quantity to send from the main store. The rest is bought.')
    qty_to_buy = fields.Float('To Buy', digits='Product Unit', compute='_compute_qty_to_buy', store=True)
    stock_move_id = fields.Many2one('stock.move', 'Store Move', copy=False, readonly=True, index='btree_not_null')
    qty_sent_from_store = fields.Float('Sent from Store', related='stock_move_id.quantity')

    def _dvz_free_in_store(self):
        self.ensure_one()
        product = self.product_id
        if not product or not product.is_storable:
            return 0.0
        company = self.company_id or self.request_id.company_id or self.env.company
        try:
            main = company._dvz_main_store()
        except UserError:
            return 0.0
        free = max(product.sudo().with_context(location=main.id).free_qty, 0.0)
        uom = self.uom_id or product.uom_id
        return product.uom_id._compute_quantity(free, uom)

    @api.depends('product_id', 'uom_id')
    def _compute_qty_free_store(self):
        for line in self:
            line.qty_free_store = line._dvz_free_in_store()

    @api.depends('product_id', 'quantity', 'uom_id')
    def _compute_qty_from_stock(self):
        for line in self:
            if line.stock_move_id or line.purchase_line_id:
                line.qty_from_stock = line.qty_from_stock
                continue
            company = line.request_id.company_id or self.env.company
            if company.dvz_mr_check_stock and company._dvz_feature('site_stores') and line.product_id.is_storable:
                line.qty_from_stock = min(line._dvz_free_in_store(), line.quantity or 0.0)
            else:
                line.qty_from_stock = 0.0

    @api.depends('quantity', 'qty_from_stock')
    def _compute_qty_to_buy(self):
        for line in self:
            line.qty_to_buy = max((line.quantity or 0.0) - (line.qty_from_stock or 0.0), 0.0)

    @api.constrains('qty_from_stock', 'quantity')
    def _check_qty_from_stock(self):
        for line in self:
            if line.qty_from_stock < 0 or line.qty_from_stock > line.quantity:
                raise ValidationError(_('"From Store" must be between 0 and the requested quantity (%s).', line.name))
