from odoo import models


class DvzRetentionRelease(models.Model):
    """Glue between Retention and Subcontractors: releasing retention held on a
    subcontract creates a vendor bill on the retention payable account."""
    _inherit = 'dvz.retention.release'

    def _is_sub(self):
        return self.contract_id.contract_type == 'subcontract'

    def _dvz_move_type(self):
        return 'in_invoice' if self._is_sub() else super()._dvz_move_type()

    def _dvz_journal(self):
        if self._is_sub():
            return self.company_id.dvz_sub_journal_id or self.env['account.journal'].search([
                ('company_id', '=', self.company_id.id), ('type', '=', 'purchase')], limit=1)
        return super()._dvz_journal()

    def _dvz_retention_account(self):
        if self._is_sub():
            return self.company_id.dvz_sub_retention_account_id
        return super()._dvz_retention_account()

    def _dvz_needs_invoice(self):
        if self._is_sub():
            return True
        return super()._dvz_needs_invoice()
