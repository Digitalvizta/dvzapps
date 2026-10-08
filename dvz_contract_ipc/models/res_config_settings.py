from odoo import fields, models


class ResConfigSettings(models.TransientModel):
    _inherit = 'res.config.settings'

    dvz_ipc_approval = fields.Boolean(related='company_id.dvz_ipc_approval', readonly=False)
    dvz_ipc_entry_mode = fields.Selection(related='company_id.dvz_ipc_entry_mode', readonly=False)
    dvz_ipc_invoice_layout = fields.Selection(related='company_id.dvz_ipc_invoice_layout', readonly=False)
    dvz_retention_method = fields.Selection(related='company_id.dvz_retention_method', readonly=False)
    dvz_ipc_journal_id = fields.Many2one(related='company_id.dvz_ipc_journal_id', readonly=False)
    dvz_ipc_product_id = fields.Many2one(related='company_id.dvz_ipc_product_id', readonly=False)
    dvz_ipc_revenue_account_id = fields.Many2one(related='company_id.dvz_ipc_revenue_account_id', readonly=False)
    dvz_retention_account_id = fields.Many2one(related='company_id.dvz_retention_account_id', readonly=False)
    dvz_advance_account_id = fields.Many2one(related='company_id.dvz_advance_account_id', readonly=False)
    dvz_deduction_account_id = fields.Many2one(related='company_id.dvz_deduction_account_id', readonly=False)
    dvz_advance_tax = fields.Boolean(related='company_id.dvz_advance_tax', readonly=False)
    dvz_recovery_tax = fields.Boolean(related='company_id.dvz_recovery_tax', readonly=False)
    dvz_allow_overrun = fields.Boolean(related='company_id.dvz_allow_overrun', readonly=False)
    dvz_ipc_auto_post = fields.Boolean(related='company_id.dvz_ipc_auto_post', readonly=False)
    dvz_ipc_bilingual = fields.Boolean(related='company_id.dvz_ipc_bilingual', readonly=False)
