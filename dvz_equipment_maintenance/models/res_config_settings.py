from odoo import fields, models


class ResConfigSettings(models.TransientModel):
    _inherit = 'res.config.settings'

    dv_eq_doc_alert_days = fields.Integer(related='company_id.dv_eq_doc_alert_days', readonly=False)
    dv_eq_service_alert_hours = fields.Float(related='company_id.dv_eq_service_alert_hours', readonly=False)
