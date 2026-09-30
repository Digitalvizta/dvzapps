from odoo import fields, models


class ResCompany(models.Model):
    _inherit = "res.company"

    dvz_vo_approval_required = fields.Boolean(string="Variations need manager approval", default=True)
    dvz_vo_auto_apply = fields.Boolean(
        string="Apply variations on approval", default=True,
        help="Update the BOQ as soon as a variation is approved. Otherwise click Apply to BOQ.")
    dvz_vo_allow_negative = fields.Boolean(
        string="Allow omissions (negative variations)", default=True)
