from odoo import fields, models


class ResConfigSettings(models.TransientModel):
    _inherit = 'res.config.settings'

    dvz_mr_approval = fields.Boolean(related='company_id.dvz_mr_approval', readonly=False)
    dvz_block_over_budget = fields.Boolean(related='company_id.dvz_block_over_budget', readonly=False)
