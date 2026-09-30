from odoo import fields, models


class ResConfigSettings(models.TransientModel):
    _inherit = "res.config.settings"

    dvz_ipc_approval_required = fields.Boolean(related="company_id.dvz_ipc_approval_required", readonly=False)
    dvz_ipc_entry_mode = fields.Selection(related="company_id.dvz_ipc_entry_mode", readonly=False)
    dvz_ipc_invoice_detail = fields.Selection(related="company_id.dvz_ipc_invoice_detail", readonly=False)
    dvz_retention_method = fields.Selection(related="company_id.dvz_retention_method", readonly=False)
    dvz_progress_product_id = fields.Many2one(related="company_id.dvz_progress_product_id", readonly=False)
    dvz_progress_account_id = fields.Many2one(related="company_id.dvz_progress_account_id", readonly=False)
    dvz_retention_account_id = fields.Many2one(related="company_id.dvz_retention_account_id", readonly=False)
    dvz_advance_account_id = fields.Many2one(related="company_id.dvz_advance_account_id", readonly=False)
    dvz_deduction_account_id = fields.Many2one(related="company_id.dvz_deduction_account_id", readonly=False)
    dvz_advance_invoice_taxed = fields.Boolean(related="company_id.dvz_advance_invoice_taxed", readonly=False)
    dvz_advance_recovery_taxed = fields.Boolean(related="company_id.dvz_advance_recovery_taxed", readonly=False)
    dvz_ipc_journal_id = fields.Many2one(related="company_id.dvz_ipc_journal_id", readonly=False)
    dvz_ipc_auto_post = fields.Boolean(related="company_id.dvz_ipc_auto_post", readonly=False)
    dvz_ipc_allow_overrun = fields.Boolean(related="company_id.dvz_ipc_allow_overrun", readonly=False)
    dvz_ipc_bilingual_report = fields.Boolean(related="company_id.dvz_ipc_bilingual_report", readonly=False)
