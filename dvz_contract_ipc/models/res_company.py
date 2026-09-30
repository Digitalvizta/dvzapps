from odoo import fields, models


class ResCompany(models.Model):
    _inherit = "res.company"

    dvz_ipc_approval_required = fields.Boolean(
        string="Certificates need manager approval", default=True)
    dvz_ipc_entry_mode = fields.Selection(
        [("qty", "Quantity done this period"), ("percent", "Cumulative % complete")],
        string="Progress entry", default="qty", required=True)
    dvz_ipc_invoice_detail = fields.Selection(
        [("summary", "One line per certificate"), ("detailed", "One line per BOQ item")],
        string="Invoice layout", default="summary", required=True)
    dvz_retention_method = fields.Selection(
        [("deduct_line", "Deduct on the invoice (negative line)"),
         ("track_only", "Invoice full amount, track retention only")],
        string="Retention method", default="deduct_line", required=True,
        help="Deduct on the invoice: the invoice shows a negative, tax-free retention line posted to the "
             "retention account.\nTrack only: the invoice is issued for the full certified amount and "
             "retention is followed in the certificate ledger (recommended when your e-invoicing, "
             "for example ZATCA, rejects negative lines).")
    dvz_progress_product_id = fields.Many2one(
        "product.product", string="Progress billing product",
        help="Product used on summary invoice lines. Its income / expense account is used unless "
             "a progress account is set below.")
    dvz_progress_account_id = fields.Many2one("account.account", string="Progress revenue account")
    dvz_retention_account_id = fields.Many2one(
        "account.account", string="Retention receivable account")
    dvz_advance_account_id = fields.Many2one(
        "account.account", string="Advance received account",
        help="Liability account credited by the advance invoice and debited by each recovery.")
    dvz_deduction_account_id = fields.Many2one(
        "account.account", string="Other deductions account")
    dvz_advance_invoice_taxed = fields.Boolean(string="Charge tax on advance invoice", default=True)
    dvz_advance_recovery_taxed = fields.Boolean(
        string="Apply tax on advance recovery", default=True,
        help="Enable when tax was charged on the advance invoice, so tax is not charged twice.")
    dvz_ipc_journal_id = fields.Many2one(
        "account.journal", string="Certificate journal", domain="[('type', '=', 'sale')]")
    dvz_ipc_auto_post = fields.Boolean(string="Post invoices automatically")
    dvz_ipc_allow_overrun = fields.Boolean(
        string="Allow quantities above BOQ",
        help="Allow cumulative certified quantity to exceed the BOQ quantity.")
    dvz_ipc_bilingual_report = fields.Boolean(string="Bilingual (English / Arabic) certificate", default=True)
