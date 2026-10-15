from odoo import _, api, fields, models
from odoo.exceptions import UserError, ValidationError
from odoo.tools import float_compare


class DvzMaterialUsage(models.Model):
    _name = 'dvz.material.usage'
    _description = 'Material Used on Site'
    _inherit = ['mail.thread', 'mail.activity.mixin']
    _order = 'date desc, id desc'
    _check_company_auto = True

    name = fields.Char('Reference', required=True, copy=False, readonly=True, default=lambda self: _('New'))
    contract_id = fields.Many2one(
        'dvz.contract', 'Contract', required=True, index=True, tracking=True, check_company=True,
        domain="[('contract_type', '=', 'client'), ('state', 'in', ('progress', 'handover')), "
               "('site_location_id', '!=', False)]")
    project_id = fields.Many2one(related='contract_id.project_id', store=True)
    site_location_id = fields.Many2one(related='contract_id.site_location_id', string='Site Store')
    company_id = fields.Many2one(related='contract_id.company_id', store=True, index=True)
    currency_id = fields.Many2one(related='company_id.currency_id', string='Currency')
    date = fields.Date('Date', required=True, default=fields.Date.context_today, tracking=True)
    user_id = fields.Many2one('res.users', 'Recorded By', default=lambda self: self.env.user, tracking=True)
    state = fields.Selection([('draft', 'Draft'), ('done', 'Done'), ('cancel', 'Cancelled')],
                             default='draft', required=True, tracking=True, copy=False, index=True)
    line_ids = fields.One2many('dvz.material.usage.line', 'usage_id', 'Materials', copy=True)
    move_ids = fields.Many2many('stock.move', 'dvz_material_usage_move_rel', 'usage_id', 'move_id',
                                'Stock Moves', copy=False, readonly=True)
    amount_total = fields.Monetary('Total Cost', compute='_compute_amount_total', store=True)
    notes = fields.Html('Notes')

    @api.depends('line_ids.subtotal')
    def _compute_amount_total(self):
        for rec in self:
            rec.amount_total = sum(rec.line_ids.mapped('subtotal'))

    @api.model_create_multi
    def create(self, vals_list):
        for vals in vals_list:
            if vals.get('name', _('New')) == _('New'):
                contract = self.env['dvz.contract'].browse(vals.get('contract_id'))
                vals['name'] = self.env['ir.sequence'].with_company(
                    contract.company_id or self.env.company).next_by_code('dvz.material.usage') or _('New')
        return super().create(vals_list)

    def unlink(self):
        if any(rec.state == 'done' for rec in self):
            raise UserError(_('Cancel the material usage before deleting it.'))
        return super().unlink()

    # ------------------------------------------------------------------
    def _dvz_make_moves(self, lines, source, dest, reverse=False):
        Move = self.env['stock.move'].sudo()
        moves = Move
        for line in lines:
            move = Move.create({
                'product_id': line.product_id.id,
                'product_uom_qty': line.quantity,
                'product_uom': (line.uom_id or line.product_id.uom_id).id,
                'location_id': source.id,
                'location_dest_id': dest.id,
                'company_id': self.company_id.id,
                'origin': self.name if not reverse else _('%s (cancelled)', self.name),
            })
            moves |= move
            if not reverse:
                line.move_id = move
        moves._action_confirm()
        moves._action_assign()
        for move in moves:
            move.quantity = move.product_uom_qty
            move.picked = True
        moves._action_done()
        return moves

    def action_done(self):
        for rec in self:
            if rec.state != 'draft':
                continue
            if not rec.company_id._dvz_feature('material_usage'):
                raise UserError(_('Material usage is switched off in Settings > Contracting > Site Stores.'))
            site = rec.contract_id.site_location_id
            if not site:
                raise UserError(_('Contract %s has no site store.', rec.contract_id.name))
            lines = rec.line_ids.filtered(lambda l: l.quantity > 0)
            if not lines:
                raise UserError(_('Add at least one material with a quantity to %s.', rec.name))
            # enough on site?
            needed = {}
            for line in lines:
                qty = (line.uom_id or line.product_id.uom_id)._compute_quantity(line.quantity, line.product_id.uom_id)
                needed[line.product_id] = needed.get(line.product_id, 0.0) + qty
            short = []
            for product, qty in needed.items():
                available = product.sudo().with_context(location=site.id).qty_available
                if float_compare(qty, available, precision_rounding=product.uom_id.rounding) > 0:
                    short.append(_('%(product)s: needed %(qty)s, on site %(available)s',
                                   product=product.display_name, qty=round(qty, 3), available=round(available, 3)))
            if short:
                raise UserError(_('Not enough material in %(site)s:\n%(lines)s',
                                  site=site.display_name, lines='\n'.join(short)))
            for line in lines:
                line.cost_unit = line._dvz_current_unit_cost()
            moves = rec._dvz_make_moves(lines, site, rec.company_id._dvz_consumption_location())
            rec.write({'state': 'done', 'move_ids': [(4, m.id) for m in moves]})
        return True

    def action_cancel(self):
        for rec in self:
            if rec.state == 'done':
                site = rec.contract_id.site_location_id
                lines = rec.line_ids.filtered(lambda l: l.move_id and l.move_id.state == 'done')
                if lines:
                    moves = rec._dvz_make_moves(lines, rec.company_id._dvz_consumption_location(), site, reverse=True)
                    rec.move_ids = [(4, m.id) for m in moves]
            rec.state = 'cancel'
        return True

    def action_draft(self):
        self.filtered(lambda r: r.state == 'cancel').write({'state': 'draft'})
        self.line_ids.write({'move_id': False})
        return True


class DvzMaterialUsageLine(models.Model):
    _name = 'dvz.material.usage.line'
    _description = 'Material Used on Site (line)'
    _order = 'usage_id, sequence, id'

    usage_id = fields.Many2one('dvz.material.usage', required=True, ondelete='cascade', index=True)
    sequence = fields.Integer(default=10)
    contract_id = fields.Many2one(related='usage_id.contract_id', store=True)
    company_id = fields.Many2one(related='usage_id.company_id', store=True)
    currency_id = fields.Many2one(related='usage_id.currency_id')
    state = fields.Selection(related='usage_id.state')
    date = fields.Date(related='usage_id.date', store=True)
    contract_line_id = fields.Many2one(
        'dvz.contract.line', 'BOQ Item', index='btree_not_null',
        domain="[('contract_id', '=', contract_id), ('display_type', '=', False)]")
    product_id = fields.Many2one('product.product', 'Material', required=True, domain="[('is_storable', '=', True)]")
    name = fields.Char('Description')
    quantity = fields.Float('Quantity', digits='Product Unit', default=1.0, required=True)
    uom_id = fields.Many2one('uom.uom', 'Unit')
    usage_type = fields.Selection([('used', 'Used'), ('wastage', 'Wastage')], default='used', required=True)
    qty_on_site = fields.Float('On Site', digits='Product Unit', compute='_compute_qty_on_site')
    cost_unit = fields.Monetary('Unit Cost', help='Product cost when the usage was confirmed.')
    subtotal = fields.Monetary('Cost', compute='_compute_subtotal', store=True)
    move_id = fields.Many2one('stock.move', 'Stock Move', copy=False, readonly=True)

    def _dvz_current_unit_cost(self):
        """Product cost per unit of this line (converted to the line unit)."""
        self.ensure_one()
        product = self.product_id.with_company(self.company_id or self.env.company)
        cost = product.standard_price
        if self.uom_id and self.uom_id != product.uom_id:
            cost = product.uom_id._compute_price(cost, self.uom_id)
        return cost

    @api.depends('quantity', 'cost_unit', 'product_id', 'uom_id', 'usage_id.state')
    def _compute_subtotal(self):
        for line in self:
            unit = line.cost_unit
            if line.usage_id.state == 'draft' and line.product_id:
                unit = line._dvz_current_unit_cost()
            line.subtotal = (line.quantity or 0.0) * (unit or 0.0)

    @api.depends('product_id', 'usage_id.contract_id.site_location_id')
    def _compute_qty_on_site(self):
        for line in self:
            site = line.usage_id.contract_id.site_location_id
            line.qty_on_site = line.product_id.sudo().with_context(location=site.id).qty_available \
                if site and line.product_id else 0.0

    @api.onchange('product_id')
    def _onchange_product_id(self):
        if self.product_id:
            self.name = self.product_id.display_name
            self.uom_id = self.product_id.uom_id

    @api.onchange('contract_line_id')
    def _onchange_contract_line_id(self):
        boq = self.contract_line_id
        if boq and boq.product_id and boq.product_id.is_storable and not self.product_id:
            self.product_id = boq.product_id

    @api.model_create_multi
    def create(self, vals_list):
        for vals in vals_list:
            if vals.get('product_id'):
                product = self.env['product.product'].browse(vals['product_id'])
                if not vals.get('name'):
                    vals['name'] = product.display_name
                if not vals.get('uom_id'):
                    vals['uom_id'] = product.uom_id.id
        return super().create(vals_list)

    @api.constrains('quantity')
    def _check_quantity(self):
        for line in self:
            if line.quantity < 0:
                raise ValidationError(_('Quantities cannot be negative.'))
