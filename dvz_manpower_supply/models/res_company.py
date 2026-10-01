from odoo import fields, models


class ResCompany(models.Model):
    _inherit = 'res.company'

    dv_daily_hours = fields.Float(string='Standard Working Hours per Day', default=8.0)
    dv_overtime_factor = fields.Float(
        string='Overtime Rate Factor', default=1.5,
        help='Saudi Labor Law: overtime is paid at basic hourly wage + 50% (factor 1.5).')
