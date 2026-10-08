from odoo import api, fields, models


class DvzContract(models.Model):
    _inherit = 'dvz.contract'

    variation_ids = fields.One2many('dvz.contract.variation', 'contract_id', 'Variations')
    variation_count = fields.Integer(compute='_compute_variation_totals')
    variation_amount = fields.Monetary('Approved Variations', compute='_compute_variation_totals')
    original_amount = fields.Monetary('Original Contract Value', compute='_compute_variation_totals')
    extension_days = fields.Integer('Time Extensions (days)', compute='_compute_variation_totals')

    @api.depends('variation_ids.state', 'variation_ids.amount_total', 'variation_ids.time_extension_days', 'amount_untaxed')
    def _compute_variation_totals(self):
        for rec in self:
            applied = rec.variation_ids.filtered(lambda v: v.state == 'applied')
            rec.variation_count = len(rec.variation_ids)
            rec.variation_amount = sum(applied.mapped('amount_total'))
            rec.original_amount = rec.amount_untaxed - rec.variation_amount
            rec.extension_days = sum(applied.mapped('time_extension_days'))

    def action_new_variation(self):
        self.ensure_one()
        return {
            'type': 'ir.actions.act_window',
            'res_model': 'dvz.contract.variation',
            'view_mode': 'form',
            'context': {'default_contract_id': self.id},
            'target': 'current',
        }

    def action_view_variations(self):
        self.ensure_one()
        action = self.env['ir.actions.act_window']._for_xml_id('dvz_contract_variation.action_dvz_variation')
        action['domain'] = [('contract_id', '=', self.id)]
        action['context'] = {'default_contract_id': self.id}
        return action
