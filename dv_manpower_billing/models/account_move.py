from odoo import fields, models


class AccountMove(models.Model):
    _inherit = 'account.move'

    dv_timesheet_id = fields.Many2one('dv.manpower.timesheet', string='Manpower Timesheet', readonly=True, copy=False)
