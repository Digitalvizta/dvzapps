from odoo import fields, models


class ResCompany(models.Model):
    _inherit = 'res.company'

    dv_eq_doc_alert_days = fields.Integer(string='Document Alert Days', default=30)
    dv_eq_service_alert_hours = fields.Float(
        string='Service Alert Hours', default=25.0,
        help='A machine is "Service due soon" when it is this many engine hours from its next service.')
