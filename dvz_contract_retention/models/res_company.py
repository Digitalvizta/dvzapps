from odoo import fields, models


class ResCompany(models.Model):
    _inherit = "res.company"

    dvz_release_auto_on_handover = fields.Boolean(string="Prepare release at handover", default=True)
    dvz_release_handover_percent = fields.Float(
        string="Released at handover (%)", default=50.0,
        help="Share of the retention held proposed for release when the works are handed over. "
             "The balance is released at the end of the defects liability period.")
    dvz_retention_reminder_days = fields.Integer(
        string="Defects period reminder (days before)", default=30)
    dvz_guarantee_reminder_days = fields.Integer(
        string="Guarantee expiry reminder (days before)", default=30)
    dvz_guarantee_auto_expire = fields.Boolean(
        string="Expire guarantees automatically", default=True,
        help="Active guarantees past their expiry date are set to Expired by the daily job.")
