from odoo import fields, models


class ResConfigSettings(models.TransientModel):
    _inherit = 'res.config.settings'

    dvz_cash_client_days = fields.Integer(related='company_id.dvz_cash_client_days', readonly=False)
    dvz_cash_vendor_days = fields.Integer(related='company_id.dvz_cash_vendor_days', readonly=False)
