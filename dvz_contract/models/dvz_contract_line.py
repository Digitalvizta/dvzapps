from odoo import _, api, fields, models
from odoo.exceptions import UserError

LOCKED_FIELDS = {'quantity', 'price_unit', 'product_id', 'uom_id', 'contract_id'}


class DvzContractLine(models.Model):
    _name = 'dvz.contract.line'
    _description = 'Contract BOQ Item'
    _order = 'contract_id, sequence, id'

    contract_id = fields.Many2one('dvz.contract', required=True, ondelete='cascade', index=True)
    company_id = fields.Many2one(related='contract_id.company_id', store=True)
    currency_id = fields.Many2one(related='contract_id.currency_id', store=True)
    contract_state = fields.Selection(related='contract_id.state')
    sequence = fields.Integer(default=10)
    display_type = fields.Selection([('line_section', 'Section'), ('line_note', 'Note')], default=False)
    item_no = fields.Char('Item No.')
    product_id = fields.Many2one('product.product', 'Product / Work Item')
    name = fields.Text('Description', required=True)
    uom_id = fields.Many2one('uom.uom', 'Unit')
    quantity = fields.Float('Quantity', digits='Product Unit', default=1.0)
    price_unit = fields.Monetary('Rate')
    price_subtotal = fields.Monetary('Amount', compute='_compute_subtotals', store=True)
    cost_unit = fields.Monetary('Est. Unit Cost')
    cost_subtotal = fields.Monetary('Est. Cost', compute='_compute_subtotals', store=True)
    margin_subtotal = fields.Monetary('Margin', compute='_compute_subtotals', store=True)

    _check_display = models.Constraint(
        "CHECK(display_type IS NOT NULL OR name IS NOT NULL)", 'Each BOQ line needs a description.')

    @api.depends('quantity', 'price_unit', 'cost_unit', 'display_type')
    def _compute_subtotals(self):
        for line in self:
            if line.display_type:
                line.price_subtotal = line.cost_subtotal = line.margin_subtotal = 0.0
                continue
            line.price_subtotal = line.quantity * line.price_unit
            line.cost_subtotal = line.quantity * line.cost_unit
            line.margin_subtotal = line.price_subtotal - line.cost_subtotal if line.cost_unit else 0.0

    @api.onchange('product_id')
    def _onchange_product_id(self):
        if self.product_id:
            self.name = self.product_id.display_name
            self.uom_id = self.product_id.uom_id
            if not self.price_unit:
                self.price_unit = self.product_id.lst_price
            if not self.cost_unit:
                self.cost_unit = self.product_id.standard_price

    def _dvz_is_locked(self):
        return (
            not self.env.context.get('dvz_boq_unlock')
            and any(line.contract_id.boq_locked for line in self)
        )

    @api.model_create_multi
    def create(self, vals_list):
        if not self.env.context.get('dvz_boq_unlock'):
            contract_ids = {v.get('contract_id') for v in vals_list if v.get('contract_id')}
            contracts = self.env['dvz.contract'].browse(list(contract_ids))
            if any(c.boq_locked for c in contracts):
                raise UserError(_('The BOQ is locked after confirmation. Use a variation order to change it.'))
        return super().create(vals_list)

    def write(self, vals):
        if LOCKED_FIELDS & set(vals) and self._dvz_is_locked():
            raise UserError(_('The BOQ is locked after confirmation. Use a variation order to change it.'))
        return super().write(vals)

    def unlink(self):
        if self._dvz_is_locked():
            raise UserError(_('The BOQ is locked after confirmation. Use a variation order to change it.'))
        return super().unlink()
