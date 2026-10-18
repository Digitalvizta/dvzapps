from odoo import fields, models


class ResConfigSettings(models.TransientModel):
    _inherit = 'res.config.settings'

    dvz_ho_overhead_percent = fields.Float(related='company_id.dvz_ho_overhead_percent', readonly=False)
    dvz_costing_method = fields.Selection(related='company_id.dvz_costing_method', readonly=False)
