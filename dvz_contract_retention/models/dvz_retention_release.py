from odoo import _, api, fields, models
from odoo.exceptions import UserError, ValidationError


class DvzRetentionRelease(models.Model):
    _name = 'dvz.retention.release'
    _description = 'Retention Release'
    _inherit = ['mail.thread', 'mail.activity.mixin']
    _order = 'date desc, id desc'
    _check_company_auto = True

    name = fields.Char('Reference', required=True, copy=False, readonly=True, default=lambda self: _('New'))
    contract_id = fields.Many2one('dvz.contract', 'Contract', required=True, index=True, tracking=True,
                                  check_company=True, domain="[('state', 'in', ('progress', 'handover', 'closed'))]")
    contract_type = fields.Selection(related='contract_id.contract_type', store=True)
    partner_id = fields.Many2one(related='contract_id.partner_id', store=True)
    company_id = fields.Many2one(related='contract_id.company_id', store=True, index=True)
    currency_id = fields.Many2one(related='contract_id.currency_id', store=True)
    date = fields.Date('Date', required=True, default=fields.Date.context_today, tracking=True)
    release_type = fields.Selection([
        ('handover', 'At handover'),
        ('dlp_end', 'End of defects period'),
        ('other', 'Other'),
    ], string='Release', required=True, default='handover', tracking=True)
    method = fields.Selection([('percent', '% of retention held'), ('amount', 'Fixed amount')],
                              required=True, default='percent')
    percent = fields.Float('% of Held', default=50.0)
    amount_input = fields.Monetary('Amount to Release')
    retention_held = fields.Monetary('Retention Held', compute='_compute_retention_held')
    amount = fields.Monetary('Release Amount', compute='_compute_amount', store=True, readonly=False, tracking=True)
    state = fields.Selection([('draft', 'Draft'), ('released', 'Released'), ('cancel', 'Cancelled')],
                             default='draft', required=True, tracking=True, copy=False)
    invoice_id = fields.Many2one('account.move', 'Release Invoice', copy=False, readonly=True)
    notes = fields.Text('Notes')

    @api.depends('contract_id')
    def _compute_retention_held(self):
        for rec in self:
            rec.retention_held = rec.contract_id.retention_held

    @api.depends('method', 'percent', 'amount_input', 'contract_id', 'release_type')
    def _compute_amount(self):
        for rec in self:
            if rec.state not in (False, 'draft'):
                rec.amount = rec.amount
                continue
            if rec.method == 'percent':
                held = rec.contract_id.retention_balance if rec.release_type == 'dlp_end' else rec.contract_id.retention_held
                rec.amount = rec.currency_id.round(held * rec.percent / 100.0) if rec.currency_id else 0.0
            else:
                rec.amount = rec.amount_input

    @api.model_create_multi
    def create(self, vals_list):
        for vals in vals_list:
            if vals.get('name', _('New')) == _('New'):
                contract = self.env['dvz.contract'].browse(vals.get('contract_id'))
                vals['name'] = self.env['ir.sequence'].with_company(contract.company_id or self.env.company).next_by_code(
                    'dvz.retention.release') or _('New')
        return super().create(vals_list)

    def unlink(self):
        if any(r.state == 'released' for r in self):
            raise UserError(_('Released retention cannot be deleted. Cancel it first.'))
        return super().unlink()

    @api.constrains('amount', 'state')
    def _check_amount(self):
        for rec in self:
            if rec.state == 'cancel':
                continue
            if rec.amount < 0:
                raise ValidationError(_('The release amount cannot be negative.'))

    # ------------------------------------------------------------------
    def _dvz_move_type(self):
        return 'out_invoice'

    def _dvz_journal(self):
        journal = self.company_id.dvz_ipc_journal_id
        if not journal:
            journal = self.env['account.journal'].search([
                ('company_id', '=', self.company_id.id), ('type', '=', 'sale')], limit=1)
        return journal

    def _dvz_retention_account(self):
        return self.company_id.dvz_retention_account_id

    def _dvz_needs_invoice(self):
        return self.company_id.dvz_retention_method == 'deduct'

    def action_release(self):
        for rec in self:
            if rec.state != 'draft':
                continue
            available = rec.contract_id.retention_balance
            if rec.currency_id.compare_amounts(rec.amount, available) > 0:
                raise UserError(_('You cannot release %(amount)s: only %(balance)s of retention is held.',
                                  amount=rec.currency_id.format(rec.amount), balance=rec.currency_id.format(available)))
            if not rec.amount:
                raise UserError(_('Nothing to release.'))
            vals = {'state': 'released'}
            if rec._dvz_needs_invoice():
                account = rec._dvz_retention_account()
                if not account:
                    raise UserError(_('Set the retention account in Settings > Contracting.'))
                journal = rec._dvz_journal()
                move = self.env['account.move'].with_company(rec.company_id).create({
                    'move_type': rec._dvz_move_type(),
                    'partner_id': rec.partner_id.id,
                    'journal_id': journal.id,
                    'currency_id': rec.currency_id.id,
                    'invoice_date': rec.date,
                    'ref': _('%(contract)s - Retention release %(name)s', contract=rec.contract_id.name, name=rec.name),
                    'invoice_origin': rec.contract_id.name,
                    'dvz_contract_id': rec.contract_id.id,
                    'dvz_move_kind': 'retention',
                    'invoice_line_ids': [(0, 0, {
                        'name': _('Retention release (%(type)s) - contract %(contract)s',
                                  type=dict(rec._fields['release_type'].selection).get(rec.release_type),
                                  contract=rec.contract_id.name),
                        'quantity': 1.0,
                        'price_unit': rec.amount,
                        'account_id': account.id,
                        'tax_ids': [(6, 0, [])],
                    })],
                })
                vals['invoice_id'] = move.id
            rec.write(vals)
        return True

    def action_cancel(self):
        for rec in self:
            if rec.invoice_id and rec.invoice_id.state == 'posted':
                raise UserError(_('The release invoice is posted. Reverse it with a credit note first.'))
            if rec.invoice_id and rec.invoice_id.state == 'draft':
                rec.invoice_id.button_cancel()
        self.write({'state': 'cancel'})
        return True

    def action_draft(self):
        self.filtered(lambda r: r.state == 'cancel').write({'state': 'draft', 'invoice_id': False})
        return True

    def action_view_invoice(self):
        self.ensure_one()
        return {'type': 'ir.actions.act_window', 'res_model': 'account.move', 'res_id': self.invoice_id.id, 'view_mode': 'form'}
