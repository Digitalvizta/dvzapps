from odoo import _, api, fields, models
from odoo.exceptions import UserError


def _dvz_sum_in(record, usage_lines):
    """Sum usage line costs (company currency) in the currency of `record` (contract or BOQ line)."""
    total = 0.0
    target = record.currency_id
    for line in usage_lines:
        amount = line.subtotal
        source = line.currency_id
        if amount and source and target and source != target:
            amount = source._convert(amount, target, line.company_id or record.company_id,
                                     line.date or fields.Date.today())
        total += amount
    return total


class DvzContract(models.Model):
    _inherit = 'dvz.contract'

    site_location_id = fields.Many2one('stock.location', 'Site Store', copy=False, readonly=True, check_company=True,
                                       help='Stock location holding the material on this contract\'s site.')
    dvz_site_stores_on = fields.Boolean(compute='_compute_dvz_site_features')
    site_stock_value = fields.Monetary('Material on Site', compute='_compute_site_stock',
                                       help='Current value of the material in the site store, at product cost.')
    site_quant_count = fields.Integer('Products on Site', compute='_compute_site_stock')
    site_transfer_count = fields.Integer('Site Transfers', compute='_compute_site_stock')
    usage_ids = fields.One2many('dvz.material.usage', 'contract_id', 'Material Usage')
    usage_count = fields.Integer(compute='_compute_usage_totals')
    material_used_cost = fields.Monetary('Material Used', compute='_compute_usage_totals')
    material_waste_cost = fields.Monetary('Material Wasted', compute='_compute_usage_totals')

    def _compute_dvz_site_features(self):
        for rec in self:
            rec.dvz_site_stores_on = (rec.company_id or self.env.company)._dvz_feature('site_stores')

    def _compute_site_stock(self):
        Quant = self.env['stock.quant'].sudo()
        Picking = self.env['stock.picking'].sudo()
        for rec in self:
            value = 0.0
            count = transfers = 0
            if rec.site_location_id:
                quants = Quant.search([('location_id', 'child_of', rec.site_location_id.id), ('quantity', '!=', 0)])
                count = len(quants.product_id)
                for quant in quants:
                    value += quant.quantity * quant.product_id.with_company(rec.company_id).standard_price
                transfers = Picking.search_count(rec._dvz_site_picking_domain())
                company_currency = rec.company_id.currency_id
                if company_currency and rec.currency_id and company_currency != rec.currency_id:
                    value = company_currency._convert(value, rec.currency_id, rec.company_id, fields.Date.today())
            rec.site_stock_value = value
            rec.site_quant_count = count
            rec.site_transfer_count = transfers

    @api.depends('usage_ids.state', 'usage_ids.line_ids.subtotal')
    def _compute_usage_totals(self):
        for rec in self:
            lines = rec.usage_ids.filtered(lambda u: u.state == 'done').line_ids
            rec.usage_count = len(rec.usage_ids)
            rec.material_used_cost = _dvz_sum_in(rec, lines.filtered(lambda l: l.usage_type == 'used'))
            rec.material_waste_cost = _dvz_sum_in(rec, lines.filtered(lambda l: l.usage_type == 'wastage'))

    # ------------------------------------------------------------------
    def _dvz_site_picking_domain(self):
        self.ensure_one()
        site = self.site_location_id
        return ['|', ('location_id', 'child_of', site.id), ('location_dest_id', 'child_of', site.id)]

    def _dvz_ensure_site_location(self):
        """Create the site store of this contract if it does not exist yet."""
        self.ensure_one()
        if self.contract_type != 'client':
            raise UserError(_('Site stores are only for client contracts. Subcontracts use the site of their '
                              'main contract.'))
        if self.site_location_id and self.site_location_id.active:
            return self.site_location_id
        parent = self.company_id._dvz_sites_parent()
        location = self.env['stock.location'].sudo().create({
            'name': self.name if not self.title else '%s - %s' % (self.name, self.title[:40]),
            'usage': 'internal',
            'location_id': parent.id,
            'company_id': self.company_id.id,
            'dvz_contract_id': self.id,
        })
        self.sudo().site_location_id = location
        self.message_post(body=_('Site store %s created.', location.display_name))
        return location

    def action_confirm(self):
        res = super().action_confirm()
        for rec in self:
            if rec.contract_type == 'client' and rec.state == 'progress' and not rec.site_location_id \
                    and rec.company_id._dvz_feature('site_stores'):
                rec._dvz_ensure_site_location()
        return res

    def action_dvz_create_site_store(self):
        for rec in self:
            rec._dvz_ensure_site_location()
        return True

    def action_dvz_view_site_stock(self):
        self.ensure_one()
        return {
            'type': 'ir.actions.act_window',
            'name': _('Stock on Site: %s', self.name),
            'res_model': 'stock.quant',
            'view_mode': 'list',
            'views': [(self.env.ref('dvz_contract_stock.dvz_site_quant_view_list').id, 'list')],
            'domain': [('location_id', 'child_of', self.site_location_id.id)],
            'context': {'search_default_group_product': 0},
        }

    def action_dvz_view_site_transfers(self):
        self.ensure_one()
        action = self.env['ir.actions.act_window']._for_xml_id('dvz_contract_stock.action_dvz_site_transfers')
        action['domain'] = self._dvz_site_picking_domain()
        action['context'] = self._dvz_transfer_context()
        action['name'] = _('Transfers: %s', self.name)
        return action

    def _dvz_transfer_context(self, dest=False):
        self.ensure_one()
        warehouse = self.company_id._dvz_warehouse()
        ctx = {
            'default_picking_type_id': warehouse.int_type_id.id,
            'default_location_id': self.site_location_id.id,
            'default_origin': self.name,
            'restricted_picking_type_code': 'internal',
        }
        if dest:
            ctx['default_location_dest_id'] = dest.id
        return ctx

    def action_dvz_new_site_transfer(self):
        """Send material from this site to another site or back to the main store."""
        self.ensure_one()
        if not self.site_location_id:
            raise UserError(_('This contract has no site store yet.'))
        return {
            'type': 'ir.actions.act_window',
            'name': _('Transfer from %s', self.name),
            'res_model': 'stock.picking',
            'view_mode': 'form',
            'context': self._dvz_transfer_context(),
        }

    def action_dvz_return_leftovers(self):
        """Prepare one transfer that returns everything left on site to the main store."""
        self.ensure_one()
        site = self.site_location_id
        if not site:
            raise UserError(_('This contract has no site store.'))
        quants = self.env['stock.quant'].search([('location_id', 'child_of', site.id), ('quantity', '>', 0)])
        if not quants:
            raise UserError(_('There is no material left in %s.', site.display_name))
        warehouse = self.company_id._dvz_warehouse()
        main = warehouse.lot_stock_id
        qty_by_product = {}
        for quant in quants:
            qty_by_product[quant.product_id] = qty_by_product.get(quant.product_id, 0.0) + quant.quantity
        picking = self.env['stock.picking'].create({
            'picking_type_id': warehouse.int_type_id.id,
            'location_id': site.id,
            'location_dest_id': main.id,
            'origin': _('%s: return to store', self.name),
            'company_id': self.company_id.id,
            'move_ids': [(0, 0, {
                'product_id': product.id,
                'product_uom_qty': qty,
                'product_uom': product.uom_id.id,
                'location_id': site.id,
                'location_dest_id': main.id,
                'company_id': self.company_id.id,
            }) for product, qty in qty_by_product.items()],
        })
        picking.action_confirm()
        picking.action_assign()
        return {
            'type': 'ir.actions.act_window',
            'res_model': 'stock.picking',
            'res_id': picking.id,
            'view_mode': 'form',
        }

    def action_dvz_view_usage(self):
        self.ensure_one()
        action = self.env['ir.actions.act_window']._for_xml_id('dvz_contract_stock.action_dvz_material_usage')
        action['domain'] = [('contract_id', '=', self.id)]
        action['context'] = {'default_contract_id': self.id}
        return action


class DvzContractLine(models.Model):
    _inherit = 'dvz.contract.line'

    usage_line_ids = fields.One2many('dvz.material.usage.line', 'contract_line_id', 'Material Usage')
    material_used_cost = fields.Monetary('Material Used', compute='_compute_material_usage', store=True)
    material_waste_cost = fields.Monetary('Material Wasted', compute='_compute_material_usage', store=True)

    @api.depends('usage_line_ids.subtotal', 'usage_line_ids.usage_type', 'usage_line_ids.usage_id.state')
    def _compute_material_usage(self):
        for line in self:
            done = line.usage_line_ids.filtered(lambda l: l.usage_id.state == 'done')
            line.material_used_cost = _dvz_sum_in(line, done.filtered(lambda l: l.usage_type == 'used'))
            line.material_waste_cost = _dvz_sum_in(line, done.filtered(lambda l: l.usage_type == 'wastage'))

    # Supplier returns reduce the ordered cost (setting). Same dependencies as the procurement module plus moves.
    @api.depends('cost_subtotal', 'display_type',
                 'purchase_line_ids.price_subtotal', 'purchase_line_ids.product_qty',
                 'purchase_line_ids.qty_received', 'purchase_line_ids.qty_invoiced',
                 'purchase_line_ids.order_id.state',
                 'request_line_ids.subtotal', 'request_line_ids.purchase_line_id', 'request_line_ids.request_id.state',
                 'purchase_line_ids.move_ids.state', 'purchase_line_ids.move_ids.quantity')
    def _compute_procurement(self):
        super()._compute_procurement()
        for line in self:
            if line.display_type or not line.company_id.dvz_returns_reduce_budget:
                continue
            returned = 0.0
            for pol in line.purchase_line_ids:
                if pol.order_id.state != 'purchase' or pol.display_type or not pol.product_qty:
                    continue
                qty = sum(m.product_uom._compute_quantity(m.quantity, pol.product_uom_id)
                          for m in pol.move_ids
                          if m.state == 'done' and m.location_dest_id.usage == 'supplier')
                if qty:
                    unit = pol._dvz_amount_in_contract_currency(pol.price_subtotal) / pol.product_qty
                    returned += unit * qty
            if not returned:
                continue
            committed = max(line.cost_committed - returned, 0.0)
            line.cost_committed = committed
            line.budget_remaining = line.cost_subtotal - committed
            line.budget_used_percent = committed / line.cost_subtotal * 100.0 if line.cost_subtotal else 0.0
            line.over_budget = bool(line.cost_subtotal and line.currency_id
                                    and line.currency_id.compare_amounts(committed, line.cost_subtotal) > 0)
