from odoo import fields, models


class ResCompany(models.Model):
    _inherit = "res.company"

    dvz_sub_journal_id = fields.Many2one(
        "account.journal", string="Subcontractor bills journal", domain="[('type', '=', 'purchase')]")
    dvz_sub_product_id = fields.Many2one("product.product", string="Subcontract work product")
    dvz_sub_expense_account_id = fields.Many2one("account.account", string="Subcontract cost account")
    dvz_sub_retention_account_id = fields.Many2one(
        "account.account", string="Retention payable account",
        help="Liability account credited with retention withheld from subcontractors.")
    dvz_sub_advance_account_id = fields.Many2one(
        "account.account", string="Advances to subcontractors account")
    dvz_sub_deduction_account_id = fields.Many2one(
        "account.account", string="Back-charges account",
        help="Income / cost-recovery account for back-charges deducted from subcontractors.")
    dvz_sub_inherit_analytic = fields.Boolean(
        string="Use main contract's analytic account", default=True,
        help="Subcontract costs are posted to the analytic account of the main contract.")
