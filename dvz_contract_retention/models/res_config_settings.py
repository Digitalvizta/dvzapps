from odoo import fields, models


class ResConfigSettings(models.TransientModel):
    _inherit = "res.config.settings"

    dvz_release_auto_on_handover = fields.Boolean(related="company_id.dvz_release_auto_on_handover", readonly=False)
    dvz_release_handover_percent = fields.Float(related="company_id.dvz_release_handover_percent", readonly=False)
    dvz_retention_reminder_days = fields.Integer(related="company_id.dvz_retention_reminder_days", readonly=False)
    dvz_guarantee_reminder_days = fields.Integer(related="company_id.dvz_guarantee_reminder_days", readonly=False)
    dvz_guarantee_auto_expire = fields.Boolean(related="company_id.dvz_guarantee_auto_expire", readonly=False)
