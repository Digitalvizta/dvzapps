from odoo import fields, models


class ResCompany(models.Model):
    _inherit = 'res.company'

    dvz_variation_approval = fields.Boolean('Variations need approval', default=True)
    dvz_variation_auto_apply = fields.Boolean('Apply variations on approval', default=True)
    dvz_variation_allow_omission = fields.Boolean('Allow omissions (negative variations)', default=True)
