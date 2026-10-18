from odoo import fields, models

WIP_METHODS = [
    ('cost', 'Cost-to-cost (cost to date ÷ forecast final cost)'),
    ('certified', 'Certified progress (approved payment certificates)'),
    ('manual', 'Entered per contract'),
]


class ResCompany(models.Model):
    _inherit = 'res.company'

    dvz_wip_method = fields.Selection(WIP_METHODS, 'Progress Method', default='cost')
    dvz_wip_journal_id = fields.Many2one('account.journal', 'WIP Journal', domain="[('type', '=', 'general')]")
    dvz_wip_revenue_account_id = fields.Many2one(
        'account.account', 'Contract Revenue (WIP adjustment)',
        help='Income account adjusted by the WIP entry. Usually the same as the work-done revenue account.')
    dvz_wip_asset_account_id = fields.Many2one(
        'account.account', 'Contract Asset (unbilled revenue)',
        help='Current asset: revenue earned but not yet certified / invoiced (under-billing).')
    dvz_wip_liability_account_id = fields.Many2one(
        'account.account', 'Contract Liability (billings in excess)',
        help='Current liability: invoiced ahead of the work done (over-billing).')
    dvz_wip_loss_account_id = fields.Many2one(
        'account.account', 'Expected Loss Expense', help='Expense for contracts forecast to make a loss.')
    dvz_wip_provision_account_id = fields.Many2one(
        'account.account', 'Provision for Contract Losses', help='Current liability for expected contract losses.')
