from odoo import fields, models


class ResCompany(models.Model):
    _inherit = 'res.company'

    dv_doc_alert_days = fields.Integer(string='Document Alert (days before expiry)', default=30)
