from odoo import _, fields, models


class RentalContract(models.Model):
    _inherit = 'dvz.rental.contract'

    logsheet_ids = fields.One2many('dvz.equipment.logsheet', 'contract_id', string='Log Sheets')
    logsheet_count = fields.Integer(compute='_compute_logsheet_count')

    def _compute_logsheet_count(self):
        for contract in self:
            contract.logsheet_count = len(contract.logsheet_ids)

    def action_view_logsheets(self):
        self.ensure_one()
        return {
            'type': 'ir.actions.act_window',
            'name': _('Log Sheets'),
            'res_model': 'dvz.equipment.logsheet',
            'view_mode': 'list,form',
            'domain': [('contract_id', '=', self.id)],
            'context': {'default_contract_id': self.id},
        }
