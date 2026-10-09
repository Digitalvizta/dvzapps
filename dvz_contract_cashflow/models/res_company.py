from odoo import fields, models


class ResCompany(models.Model):
    _inherit = 'res.company'

    dvz_cash_client_days = fields.Integer('Clients pay after (days)', default=60)
    dvz_cash_vendor_days = fields.Integer('We pay vendors after (days)', default=30)
