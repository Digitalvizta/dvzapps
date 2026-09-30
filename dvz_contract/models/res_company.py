from odoo import fields, models


class ResCompany(models.Model):
    _inherit = "res.company"

    dvz_retention_percent = fields.Float(
        string="Default retention (%)", default=10.0,
        help="Percentage withheld from each payment certificate until handover / end of defects period.")
    dvz_advance_percent = fields.Float(
        string="Default advance payment (%)", default=0.0,
        help="Advance payment as a percentage of the contract value.")
    dvz_advance_recovery_percent = fields.Float(
        string="Default advance recovery (%)", default=0.0,
        help="Percentage of each certificate's gross amount deducted to recover the advance payment.")
    dvz_dlp_months = fields.Integer(
        string="Default defects liability period (months)", default=12)
    dvz_auto_analytic = fields.Boolean(
        string="Create analytic account per contract", default=True,
        help="When a contract is confirmed, create (or reuse the project's) analytic account to track cost and revenue.")
    dvz_analytic_plan_id = fields.Many2one(
        "account.analytic.plan", string="Analytic plan for contracts",
        help="Plan used for automatically created contract analytic accounts. Empty = the project plan.")
    dvz_sale_tax_id = fields.Many2one(
        "account.tax", string="Default tax on client contracts",
        domain="[('type_tax_use', '=', 'sale')]")
    dvz_purchase_tax_id = fields.Many2one(
        "account.tax", string="Default tax on subcontracts",
        domain="[('type_tax_use', '=', 'purchase')]")
    dvz_lock_boq = fields.Boolean(
        string="Lock BOQ after confirmation", default=True,
        help="Once a contract is confirmed its BOQ cannot be edited; changes go through variation orders.")
