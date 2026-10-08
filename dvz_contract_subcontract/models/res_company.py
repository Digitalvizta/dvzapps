from odoo import fields, models


class ResCompany(models.Model):
    _inherit = 'res.company'

    dvz_sub_use_main_analytic = fields.Boolean("Use main contract's analytic account", default=True)
    dvz_sub_journal_id = fields.Many2one('account.journal', 'Subcontractor bills journal', domain=[('type', '=', 'purchase')])
    dvz_sub_product_id = fields.Many2one('product.product', 'Subcontract work product')
    dvz_sub_cost_account_id = fields.Many2one('account.account', 'Subcontract cost account')
    dvz_sub_retention_account_id = fields.Many2one('account.account', 'Retention payable account')
    dvz_sub_advance_account_id = fields.Many2one('account.account', 'Advances paid account')
    dvz_sub_backcharge_account_id = fields.Many2one('account.account', 'Back-charges account')
