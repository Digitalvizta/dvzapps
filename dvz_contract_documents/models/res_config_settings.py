from odoo import fields, models


class ResConfigSettings(models.TransientModel):
    _inherit = 'res.config.settings'

    dvz_rfi_days = fields.Integer(related='company_id.dvz_rfi_days', readonly=False)
    dvz_submittal_days = fields.Integer(related='company_id.dvz_submittal_days', readonly=False)
