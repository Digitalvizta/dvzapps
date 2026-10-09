from odoo import _, api, fields, models
from odoo.exceptions import UserError


class DvzContract(models.Model):
    _inherit = 'dvz.contract'

    certificate_ids = fields.One2many('dvz.contract.certificate', 'contract_id', 'Payment Certificates')
    certificate_count = fields.Integer(compute='_compute_billing')
    certified_amount = fields.Monetary('Certified to Date', compute='_compute_billing')
    certified_percent = fields.Float('Certified %', compute='_compute_billing')
    retention_held = fields.Monetary('Retention Held', compute='_compute_billing')
    advance_move_ids = fields.One2many('account.move', 'dvz_contract_id', 'Contract Invoices')
    advance_amount = fields.Monetary('Advance Invoiced', compute='_compute_advance', compute_sudo=True)
    advance_recovered = fields.Monetary('Advance Recovered', compute='_compute_billing')
    advance_balance = fields.Monetary('Advance to Recover', compute='_compute_billing')
    amount_to_certify = fields.Monetary('Remaining to Certify', compute='_compute_billing')

    @api.depends('advance_move_ids.state', 'advance_move_ids.amount_untaxed', 'advance_move_ids.dvz_move_kind')
    def _compute_advance(self):
        for rec in self:
            moves = rec.advance_move_ids.filtered(lambda m: m.dvz_move_kind == 'advance' and m.state != 'cancel')
            rec.advance_amount = sum(moves.mapped('amount_untaxed'))

    @api.depends('certificate_ids.state', 'certificate_ids.amount_current', 'certificate_ids.retention_amount',
                 'certificate_ids.advance_recovery_amount', 'amount_untaxed', 'advance_amount')
    def _compute_billing(self):
        for rec in self:
            certs = rec.certificate_ids.filtered(lambda c: c.state in ('approved', 'invoiced'))
            live = rec.certificate_ids.filtered(lambda c: c.state != 'cancel')
            certified = sum(certs.mapped('amount_current'))
            rec.certificate_count = len(rec.certificate_ids)
            rec.certified_amount = certified
            rec.certified_percent = certified / rec.amount_untaxed * 100.0 if rec.amount_untaxed else 0.0
            rec.retention_held = sum(certs.mapped('retention_amount'))
            rec.advance_recovered = sum(live.mapped('advance_recovery_amount'))
            rec.advance_balance = rec.advance_amount - rec.advance_recovered
            rec.amount_to_certify = rec.amount_untaxed - certified

    def action_new_certificate(self):
        self.ensure_one()
        if self.state not in ('progress', 'handover'):
            raise UserError(_('Confirm the contract before creating certificates.'))
        if self.certificate_ids.filtered(lambda c: c.state in ('draft', 'submitted')):
            raise UserError(_('Finish or cancel the open certificate before starting a new one.'))
        last = self.certificate_ids.filtered(lambda c: c.state != 'cancel').sorted('date')[-1:]
        cert = self.env['dvz.contract.certificate'].create({
            'contract_id': self.id,
            'period_start': last.period_end and fields.Date.add(last.period_end, days=1) or self.date_start,
            'period_end': fields.Date.context_today(self),
        })
        return {
            'type': 'ir.actions.act_window',
            'res_model': 'dvz.contract.certificate',
            'res_id': cert.id,
            'view_mode': 'form',
            'target': 'current',
        }

    def action_view_certificates(self):
        self.ensure_one()
        action = self.env['ir.actions.act_window']._for_xml_id('dvz_contract_ipc.action_dvz_certificate')
        action['domain'] = [('contract_id', '=', self.id)]
        action['context'] = {'default_contract_id': self.id}
        return action

    def action_view_invoices(self):
        self.ensure_one()
        moves = self.env['account.move'].search([('dvz_contract_id', '=', self.id)])
        return {
            'type': 'ir.actions.act_window',
            'name': _('Invoices'),
            'res_model': 'account.move',
            'view_mode': 'list,form',
            'domain': [('id', 'in', moves.ids)],
        }

    # ------------------------------------------------------------------
    # Advance payment invoice
    # ------------------------------------------------------------------
    def _dvz_advance_move_type(self):
        return 'out_invoice'

    def _dvz_advance_journal(self):
        journal = self.company_id.dvz_ipc_journal_id
        if not journal:
            journal = self.env['account.journal'].search([
                ('company_id', '=', self.company_id.id), ('type', '=', 'sale')], limit=1)
        return journal

    def _dvz_advance_account(self):
        return self.company_id.dvz_advance_account_id

    def _dvz_advance_taxes(self):
        return self.tax_ids if self.company_id.dvz_advance_tax else self.env['account.tax']

    def action_create_advance_invoice(self):
        self.ensure_one()
        if self.state != 'progress':
            raise UserError(_('The contract must be in progress.'))
        if not self.advance_percent:
            raise UserError(_('Set an advance payment % on the contract first.'))
        if self.advance_move_ids.filtered(lambda m: m.dvz_move_kind == 'advance' and m.state != 'cancel'):
            raise UserError(_('An advance invoice already exists for this contract.'))
        account = self._dvz_advance_account()
        if not account:
            raise UserError(_('Set the advance account in Settings > Contracting.'))
        journal = self._dvz_advance_journal()
        if not journal:
            raise UserError(_('Set a journal in Settings > Contracting.'))
        amount = self.currency_id.round(self.amount_untaxed * self.advance_percent / 100.0)
        move = self.env['account.move'].with_company(self.company_id).create({
            'move_type': self._dvz_advance_move_type(),
            'partner_id': self.partner_id.id,
            'journal_id': journal.id,
            'currency_id': self.currency_id.id,
            'invoice_date': fields.Date.context_today(self),
            'ref': _('%s - Advance payment', self.name),
            'invoice_origin': self.name,
            'dvz_contract_id': self.id,
            'dvz_move_kind': 'advance',
            'invoice_line_ids': [(0, 0, {
                'name': _('Advance payment %(pct)s%% - contract %(name)s', pct=self.advance_percent, name=self.name),
                'quantity': 1.0,
                'price_unit': amount,
                'account_id': account.id,
                'tax_ids': [(6, 0, self._dvz_advance_taxes().ids)],
            })],
        })
        return {
            'type': 'ir.actions.act_window',
            'res_model': 'account.move',
            'res_id': move.id,
            'view_mode': 'form',
        }
