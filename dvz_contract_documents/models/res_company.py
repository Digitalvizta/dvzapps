from odoo import fields, models


class ResCompany(models.Model):
    _inherit = 'res.company'

    dvz_rfi_days = fields.Integer('RFI answer time (days)', default=7)
    dvz_submittal_days = fields.Integer('Submittal review time (days)', default=14)
