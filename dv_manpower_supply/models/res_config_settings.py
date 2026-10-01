from odoo import fields, models


class ResConfigSettings(models.TransientModel):
    _inherit = 'res.config.settings'

    dv_daily_hours = fields.Float(related='company_id.dv_daily_hours', readonly=False)
    dv_overtime_factor = fields.Float(related='company_id.dv_overtime_factor', readonly=False)
