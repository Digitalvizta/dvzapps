from odoo import _, api, models
from odoo.exceptions import UserError


class DvzContractCertificate(models.Model):
    _inherit = 'dvz.contract.certificate'

    @api.model
    def _dvz_sequence_code(self, contract):
        if contract and contract.contract_type == 'subcontract':
            return 'dvz.contract.certificate.sub'
        return super()._dvz_sequence_code(contract)

    def _is_sub(self):
        return self.contract_id.contract_type == 'subcontract'

    def _dvz_move_type(self):
        return 'in_invoice' if self._is_sub() else super()._dvz_move_type()

    def _dvz_journal(self):
        if not self._is_sub():
            return super()._dvz_journal()
        journal = self.company_id.dvz_sub_journal_id or self.env['account.journal'].search([
            ('company_id', '=', self.company_id.id), ('type', '=', 'purchase')], limit=1)
        if not journal:
            raise UserError(_('Set the subcontractor bills journal in Settings > Contracting.'))
        return journal

    def _dvz_accounts(self):
        res = super()._dvz_accounts()
        if self._is_sub():
            company = self.company_id
            res.update({
                'product': company.dvz_sub_product_id,
                'work': company.dvz_sub_cost_account_id,
                'retention': company.dvz_sub_retention_account_id,
                'advance': company.dvz_sub_advance_account_id,
                'deduction': company.dvz_sub_backcharge_account_id,
                'retention_method': 'deduct',
            })
        return res

    def _prepare_invoice_vals(self):
        vals = super()._prepare_invoice_vals()
        if self._is_sub():
            vals['invoice_date'] = self.date
            vals['ref'] = '%s - %s' % (self.contract_id.name, self.name)
        return vals
