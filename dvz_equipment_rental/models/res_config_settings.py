from odoo import fields, models


class ResConfigSettings(models.TransientModel):
    _inherit = 'res.config.settings'

    dv_eq_daily_hours = fields.Float(related='company_id.dv_eq_daily_hours', readonly=False)
    dv_eq_week_days = fields.Integer(related='company_id.dv_eq_week_days', readonly=False)
    dv_eq_extra_factor = fields.Float(related='company_id.dv_eq_extra_factor', readonly=False)
