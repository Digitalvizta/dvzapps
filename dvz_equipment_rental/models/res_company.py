from odoo import fields, models


class ResCompany(models.Model):
    _inherit = 'res.company'

    dv_eq_daily_hours = fields.Float(
        string='Standard Equipment Hours per Day', default=10.0,
        help='Hours included in a daily rate. Also used to fill log sheets.\n'
             'Monthly rates are prorated on the working days of each month (Fridays excluded).')
    dv_eq_week_days = fields.Integer(string='Standard Working Days per Week', default=6)
    dv_eq_extra_factor = fields.Float(
        string='Extra Hours Rate Factor', default=1.0,
        help='Hours above the standard daily hours are billed at the hourly equivalent x this factor.')
