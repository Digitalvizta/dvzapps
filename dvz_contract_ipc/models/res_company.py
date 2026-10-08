from odoo import fields, models


class ResCompany(models.Model):
    _inherit = 'res.company'

    dvz_ipc_approval = fields.Boolean('Certificates need approval', default=True)
    dvz_ipc_entry_mode = fields.Selection(
        [('qty', 'Quantity this period'), ('percent', 'Cumulative % complete')],
        string='Progress entry', default='qty', required=True)
    dvz_ipc_invoice_layout = fields.Selection(
        [('summary', 'One summary line'), ('detailed', 'One line per BOQ item')],
        string='Invoice layout', default='summary', required=True)
    dvz_retention_method = fields.Selection(
        [('deduct', 'Deduct on invoice'), ('track', 'Track only (invoice full amount)')],
        string='Retention method', default='deduct', required=True)
    dvz_ipc_journal_id = fields.Many2one('account.journal', 'Certificates journal', domain=[('type', '=', 'sale')])
    dvz_ipc_product_id = fields.Many2one('product.product', 'Work done product')
    dvz_ipc_revenue_account_id = fields.Many2one('account.account', 'Revenue account (work done)')
    dvz_retention_account_id = fields.Many2one('account.account', 'Retention receivable account')
    dvz_advance_account_id = fields.Many2one('account.account', 'Advances received account')
    dvz_deduction_account_id = fields.Many2one('account.account', 'Deductions account')
    dvz_advance_tax = fields.Boolean('Tax on advance invoice', default=True)
    dvz_recovery_tax = fields.Boolean('Tax on advance recovery', default=True)
    dvz_allow_overrun = fields.Boolean('Allow quantities above BOQ', default=False)
    dvz_ipc_auto_post = fields.Boolean('Post invoices automatically', default=False)
    dvz_ipc_bilingual = fields.Boolean('Bilingual certificate (English / Arabic)', default=True)
