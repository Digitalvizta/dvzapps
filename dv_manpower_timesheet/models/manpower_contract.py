from odoo import _, fields, models


class ManpowerContract(models.Model):
    _inherit = 'dv.manpower.contract'

    timesheet_ids = fields.One2many('dv.manpower.timesheet', 'contract_id', string='Timesheets')
    timesheet_count = fields.Integer(compute='_compute_timesheet_count')

    def _compute_timesheet_count(self):
        for contract in self:
            contract.timesheet_count = len(contract.timesheet_ids)

    def action_view_timesheets(self):
        self.ensure_one()
        return {
            'type': 'ir.actions.act_window',
            'name': _('Timesheets'),
            'res_model': 'dv.manpower.timesheet',
            'view_mode': 'list,form',
            'domain': [('contract_id', '=', self.id)],
            'context': {'default_contract_id': self.id},
        }
