from collections import defaultdict
from datetime import datetime, time

from odoo import _, api, fields, models
from odoo.exceptions import UserError


class DvzMaterialRequest(models.Model):
    _name = 'dvz.material.request'
    _description = 'Material Request'
    _inherit = ['mail.thread', 'mail.activity.mixin']
    _order = 'date desc, id desc'
    _check_company_auto = True

    name = fields.Char('Reference', required=True, copy=False, readonly=True, default=lambda self: _('New'))
    contract_id = fields.Many2one(
        'dvz.contract', 'Contract', required=True, index=True, tracking=True, check_company=True,
        domain="[('contract_type', '=', 'client'), ('state', 'in', ('progress', 'handover'))]")
    project_id = fields.Many2one(related='contract_id.project_id', store=True)
    company_id = fields.Many2one(related='contract_id.company_id', store=True, index=True)
    currency_id = fields.Many2one(related='contract_id.currency_id', store=True)
    user_id = fields.Many2one('res.users', 'Requested By', default=lambda self: self.env.user, tracking=True)
    date = fields.Date('Request Date', required=True, default=fields.Date.context_today, tracking=True)
    date_required = fields.Date('Required On Site', tracking=True)
    location = fields.Char('Site Area / Delivery Point')
    state = fields.Selection([
        ('draft', 'Draft'),
        ('submitted', 'To Approve'),
        ('approved', 'Approved'),
        ('ordered', 'Ordered'),
        ('cancel', 'Cancelled'),
    ], default='draft', required=True, tracking=True, copy=False, index=True)
    line_ids = fields.One2many('dvz.material.request.line', 'request_id', 'Materials', copy=True)
    amount_estimated = fields.Monetary('Estimated Cost', compute='_compute_amount_estimated', store=True)
    purchase_ids = fields.Many2many('purchase.order', compute='_compute_purchase_ids', string='Purchase Orders')
    purchase_count = fields.Integer(compute='_compute_purchase_ids')
    over_budget = fields.Boolean('Over Budget', compute='_compute_over_budget',
                                 help='At least one line takes its BOQ item over the cost budget.')
    approved_by_id = fields.Many2one('res.users', 'Approved By', copy=False, readonly=True)
    approved_date = fields.Date('Approved On', copy=False, readonly=True)
    notes = fields.Html('Notes')

    @api.depends('line_ids.subtotal')
    def _compute_amount_estimated(self):
        for rec in self:
            rec.amount_estimated = sum(rec.line_ids.mapped('subtotal'))

    def _compute_purchase_ids(self):
        PO = self.env['purchase.order'].sudo()
        for rec in self:
            orders = PO.search([('dvz_material_request_id', '=', rec.id)]) if rec.id else PO
            rec.purchase_ids = orders
            rec.purchase_count = len(orders)

    @api.depends('line_ids.over_budget')
    def _compute_over_budget(self):
        for rec in self:
            rec.over_budget = any(rec.line_ids.mapped('over_budget'))

    @api.model_create_multi
    def create(self, vals_list):
        for vals in vals_list:
            if vals.get('name', _('New')) == _('New'):
                contract = self.env['dvz.contract'].browse(vals.get('contract_id'))
                vals['name'] = self.env['ir.sequence'].with_company(
                    contract.company_id or self.env.company).next_by_code('dvz.material.request') or _('New')
        return super().create(vals_list)

    def unlink(self):
        if any(rec.state not in ('draft', 'cancel') for rec in self):
            raise UserError(_('Only draft or cancelled material requests can be deleted.'))
        return super().unlink()

    # ------------------------------------------------------------------
    def action_submit(self):
        for rec in self:
            if rec.state != 'draft':
                continue
            if not rec.line_ids:
                raise UserError(_('Add at least one material to %s.', rec.name))
            if rec.company_id.dvz_mr_approval:
                rec.state = 'submitted'
                manager = rec.contract_id.user_id
                if manager:
                    rec.activity_schedule('mail.mail_activity_data_todo', user_id=manager.id,
                                          summary=_('Approve material request %s', rec.name))
            else:
                rec._do_approve()
        return True

    def _do_approve(self):
        self.write({'state': 'approved', 'approved_by_id': self.env.user.id,
                    'approved_date': fields.Date.context_today(self)})
        self.activity_feedback(['mail.mail_activity_data_todo'])

    def action_approve(self):
        if not self.env.user.has_group('dvz_contract.group_dvz_contract_manager'):
            raise UserError(_('Only contracting managers can approve material requests.'))
        self.filtered(lambda r: r.state == 'submitted')._do_approve()
        return True

    def action_cancel(self):
        for rec in self:
            if rec.line_ids.filtered(lambda l: l.purchase_line_id and l.purchase_line_id.order_id.state == 'purchase'):
                raise UserError(_('%s already has confirmed purchase orders. Cancel them first.', rec.name))
        self.activity_unlink(['mail.mail_activity_data_todo'])
        self.write({'state': 'cancel'})
        return True

    def action_draft(self):
        self.filtered(lambda r: r.state in ('submitted', 'cancel')).write({'state': 'draft'})
        return True

    # ------------------------------------------------------------------
    def _dvz_vendor(self, line):
        if line.vendor_id:
            return line.vendor_id
        seller = line.product_id.with_company(self.company_id)._select_seller(
            quantity=line.quantity, uom_id=line.uom_id or line.product_id.uom_id)
        return seller.partner_id

    def action_create_rfq(self):
        self.ensure_one()
        if self.state != 'approved':
            raise UserError(_('Approve the material request before creating requests for quotation.'))
        if not self.env['purchase.order'].has_access('create'):
            raise UserError(_('Only purchase users can create requests for quotation.'))
        lines = self.line_ids.filtered(lambda l: not l.purchase_line_id)
        if not lines:
            raise UserError(_('All materials of %s are already on purchase orders.', self.name))
        by_vendor = defaultdict(lambda: self.env['dvz.material.request.line'])
        for line in lines:
            vendor = self._dvz_vendor(line)
            if not vendor:
                raise UserError(_('Set a vendor on "%s" (or a vendor price on the product).', line.name))
            by_vendor[vendor] |= line

        analytic = self.contract_id.analytic_account_id
        planned = datetime.combine(self.date_required or fields.Date.context_today(self), time(12, 0))
        orders = self.env['purchase.order']
        for vendor, vlines in by_vendor.items():
            order = self.env['purchase.order'].with_company(self.company_id).create({
                'partner_id': vendor.id,
                'company_id': self.company_id.id,
                'origin': self.name,
                'dvz_contract_id': self.contract_id.id,
                'dvz_material_request_id': self.id,
            })
            for line in vlines:
                vals = {
                    'order_id': order.id,
                    'product_id': line.product_id.id,
                    'name': line.name or line.product_id.display_name,
                    'product_qty': line.quantity,
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
        self.state = 'ordered'
        self.message_post(body=_('Requests for quotation created: %s', ', '.join(orders.mapped('name'))))
        return self.action_view_purchases()

    def action_view_purchases(self):
        self.ensure_one()
        action = {
            'type': 'ir.actions.act_window',
            'name': _('Purchase Orders'),
            'res_model': 'purchase.order',
            'view_mode': 'list,form',
            'domain': [('dvz_material_request_id', '=', self.id)],
            'context': {'default_dvz_contract_id': self.contract_id.id, 'default_dvz_material_request_id': self.id},
        }
        if self.purchase_count == 1:
            action.update({'view_mode': 'form', 'res_id': self.purchase_ids.id})
        return action


class DvzMaterialRequestLine(models.Model):
    _name = 'dvz.material.request.line'
    _description = 'Material Request Line'
    _order = 'request_id, sequence, id'

    request_id = fields.Many2one('dvz.material.request', required=True, ondelete='cascade', index=True)
    sequence = fields.Integer(default=10)
    contract_id = fields.Many2one(related='request_id.contract_id', store=True)
    company_id = fields.Many2one(related='request_id.company_id', store=True)
    currency_id = fields.Many2one(related='request_id.currency_id', store=True)
    state = fields.Selection(related='request_id.state')
    contract_line_id = fields.Many2one(
        'dvz.contract.line', 'BOQ Item', index='btree_not_null',
        domain="[('contract_id', '=', contract_id), ('display_type', '=', False)]")
    product_id = fields.Many2one('product.product', 'Material', required=True,
                                 domain="[('purchase_ok', '=', True)]")
    name = fields.Char('Description')
    quantity = fields.Float('Quantity', digits='Product Unit', default=1.0, required=True)
    uom_id = fields.Many2one('uom.uom', 'Unit')
    price_unit = fields.Monetary('Est. Unit Cost')
    subtotal = fields.Monetary('Est. Cost', compute='_compute_subtotal', store=True)
    vendor_id = fields.Many2one('res.partner', 'Vendor')
    purchase_line_id = fields.Many2one('purchase.order.line', 'Purchase Line', copy=False, readonly=True,
                                       index='btree_not_null')
    purchase_id = fields.Many2one(related='purchase_line_id.order_id', string='Purchase Order')
    qty_ordered = fields.Float(related='purchase_line_id.product_qty', string='Ordered')
    qty_received = fields.Float(related='purchase_line_id.qty_received', string='Received')
    budget_remaining = fields.Monetary(related='contract_line_id.budget_remaining', string='BOQ Budget Left')
    over_budget = fields.Boolean(compute='_compute_over_budget')

    @api.depends('quantity', 'price_unit')
    def _compute_subtotal(self):
        for line in self:
            line.subtotal = line.quantity * line.price_unit

    @api.depends('subtotal', 'contract_line_id.budget_remaining', 'contract_line_id.cost_subtotal', 'purchase_line_id')
    def _compute_over_budget(self):
        for line in self:
            boq = line.contract_line_id
            line.over_budget = bool(
                boq and boq.cost_subtotal and not line.purchase_line_id
                and line.currency_id and line.currency_id.compare_amounts(line.subtotal, boq.budget_remaining) > 0)

    @api.onchange('product_id')
    def _onchange_product_id(self):
        product = self.product_id
        if not product:
            return
        self.name = product.display_name
        self.uom_id = product.uom_id
        seller = product._select_seller(quantity=self.quantity or 1.0)
        if seller:
            self.vendor_id = seller.partner_id
            self.price_unit = seller.price
        else:
            self.price_unit = product.standard_price

    @api.onchange('contract_line_id')
    def _onchange_contract_line_id(self):
        boq = self.contract_line_id
        if boq and boq.product_id and not self.product_id:
            self.product_id = boq.product_id

    @api.model_create_multi
    def create(self, vals_list):
        for vals in vals_list:
            if vals.get('product_id') and (not vals.get('name') or not vals.get('uom_id')):
                product = self.env['product.product'].browse(vals['product_id'])
                vals.setdefault('name', product.display_name)
                if not vals.get('name'):
                    vals['name'] = product.display_name
                if not vals.get('uom_id'):
                    vals['uom_id'] = product.uom_id.id
            if vals.get('product_id') and 'price_unit' not in vals:
                vals['price_unit'] = self.env['product.product'].browse(vals['product_id']).standard_price
        return super().create(vals_list)
