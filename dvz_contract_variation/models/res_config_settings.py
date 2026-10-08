from odoo import fields, models


class ResConfigSettings(models.TransientModel):
    _inherit = 'res.config.settings'

    dvz_variation_approval = fields.Boolean(related='company_id.dvz_variation_approval', readonly=False)
    dvz_variation_auto_apply = fields.Boolean(related='company_id.dvz_variation_auto_apply', readonly=False)
    dvz_variation_allow_omission = fields.Boolean(related='company_id.dvz_variation_allow_omission', readonly=False)
