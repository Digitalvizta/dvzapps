from odoo import fields, models


class ResConfigSettings(models.TransientModel):
    _inherit = 'res.config.settings'

    dv_doc_alert_days = fields.Integer(related='company_id.dv_doc_alert_days', readonly=False)
