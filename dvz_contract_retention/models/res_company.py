from odoo import fields, models


class ResCompany(models.Model):
    _inherit = 'res.company'

    dvz_release_at_handover = fields.Boolean('Prepare retention release at handover', default=True)
    dvz_release_handover_percent = fields.Float('Release at handover (% of held)', default=50.0)
    dvz_dlp_reminder_days = fields.Integer('Defects period reminder (days before)', default=30)
    dvz_guarantee_reminder_days = fields.Integer('Guarantee expiry reminder (days before)', default=30)
    dvz_guarantee_auto_expire = fields.Boolean('Expire guarantees automatically', default=True)
