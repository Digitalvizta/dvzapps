from odoo import fields, models


class ResConfigSettings(models.TransientModel):
    _inherit = 'res.config.settings'

    dv_eq_fuel_price = fields.Float(related='company_id.dv_eq_fuel_price', readonly=False)
