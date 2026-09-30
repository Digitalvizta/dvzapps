from odoo import fields, models


class ResConfigSettings(models.TransientModel):
    _inherit = "res.config.settings"

    dvz_vo_approval_required = fields.Boolean(related="company_id.dvz_vo_approval_required", readonly=False)
    dvz_vo_auto_apply = fields.Boolean(related="company_id.dvz_vo_auto_apply", readonly=False)
    dvz_vo_allow_negative = fields.Boolean(related="company_id.dvz_vo_allow_negative", readonly=False)
