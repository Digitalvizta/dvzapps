from odoo import fields, models


class ResConfigSettings(models.TransientModel):
    _inherit = 'res.config.settings'

    dvz_sub_use_main_analytic = fields.Boolean(related='company_id.dvz_sub_use_main_analytic', readonly=False)
    dvz_sub_journal_id = fields.Many2one(related='company_id.dvz_sub_journal_id', readonly=False)
    dvz_sub_product_id = fields.Many2one(related='company_id.dvz_sub_product_id', readonly=False)
    dvz_sub_cost_account_id = fields.Many2one(related='company_id.dvz_sub_cost_account_id', readonly=False)
    dvz_sub_retention_account_id = fields.Many2one(related='company_id.dvz_sub_retention_account_id', readonly=False)
    dvz_sub_advance_account_id = fields.Many2one(related='company_id.dvz_sub_advance_account_id', readonly=False)
    dvz_sub_backcharge_account_id = fields.Many2one(related='company_id.dvz_sub_backcharge_account_id', readonly=False)
