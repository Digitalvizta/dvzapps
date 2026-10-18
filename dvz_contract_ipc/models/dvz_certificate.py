from odoo import _, api, fields, models
from odoo.exceptions import UserError, ValidationError
from odoo.tools import float_compare, float_is_zero


class DvzContractCertificate(models.Model):
    _name = 'dvz.contract.certificate'
    _description = 'Interim Payment Certificate'
    _inherit = ['mail.thread', 'mail.activity.mixin']
    _order = 'date desc, id desc'
    _check_company_auto = True

    name = fields.Char('Reference', required=True, copy=False, readonly=True, default=lambda self: _('New'))
    contract_id = fields.Many2one(
        'dvz.contract', 'Contract', required=True, index=True, tracking=True, check_company=True,
        domain="[('state', 'in', ('progress', 'handover'))]")
    contract_type = fields.Selection(related='contract_id.contract_type', store=True)
    number = fields.Integer('Certificate No.', copy=False, readonly=True)
    partner_id = fields.Many2one(related='contract_id.partner_id', store=True)
    project_id = fields.Many2one(related='contract_id.project_id', store=True)
    company_id = fields.Many2one(related='contract_id.company_id', store=True, index=True)
    currency_id = fields.Many2one(related='contract_id.currency_id', store=True)
    date = fields.Date('Certificate Date', required=True, default=fields.Date.context_today, tracking=True)
    period_start = fields.Date('Period From')
    period_end = fields.Date('Period To')
    state = fields.Selection([
        ('draft', 'Draft'),
        ('submitted', 'Submitted'),
        ('approved', 'Approved'),
        ('invoiced', 'Invoiced'),
        ('cancel', 'Cancelled'),
    ], default='draft', required=True, tracking=True, copy=False, index=True)
    entry_mode = fields.Selection(related='company_id.dvz_ipc_entry_mode')
    line_ids = fields.One2many('dvz.contract.certificate.line', 'certificate_id', 'Progress', copy=True)
    deduction_ids = fields.One2many('dvz.contract.certificate.deduction', 'certificate_id', 'Deduction Lines', copy=True)

    amount_previous = fields.Monetary('Previously Certified', compute='_compute_amounts', store=True)
    amount_current = fields.Monetary('Work Done This Period', compute='_compute_amounts', store=True)
    amount_cumulative = fields.Monetary('Cumulative Work Done', compute='_compute_amounts', store=True)
    retention_percent = fields.Float('Retention %', readonly=True, copy=False)
    retention_amount = fields.Monetary('Retention', compute='_compute_amounts', store=True)
    advance_recovery_percent = fields.Float('Advance Recovery %', readonly=True, copy=False)
    advance_recovery_amount = fields.Monetary('Advance Recovery', compute='_compute_amounts', store=True)
    deduction_amount = fields.Monetary('Other Deductions', compute='_compute_amounts', store=True)
    amount_due = fields.Monetary('Net Amount Due (excl. tax)', compute='_compute_amounts', store=True)
    progress_percent = fields.Float('Cumulative Progress %', compute='_compute_amounts', store=True)

    invoice_id = fields.Many2one('account.move', 'Invoice', copy=False, readonly=True)
    invoice_state = fields.Selection(related='invoice_id.state', string='Invoice Status')
    approved_by_id = fields.Many2one('res.users', 'Approved By', copy=False, readonly=True)
    approved_date = fields.Date('Approved On', copy=False, readonly=True)
    consultant = fields.Char('Consultant / Engineer')
    notes = fields.Html('Notes')

    # ------------------------------------------------------------------
    @api.depends('line_ids.amount_previous', 'line_ids.amount_current', 'line_ids.amount_cumulative',
                 'deduction_ids.amount', 'retention_percent', 'advance_recovery_percent', 'contract_id')
    def _compute_amounts(self):
        for cert in self:
            lines = cert.line_ids.filtered(lambda l: not l.display_type)
            prev = sum(lines.mapped('amount_previous'))
            cur = sum(lines.mapped('amount_current'))
            cum = sum(lines.mapped('amount_cumulative'))
            retention = cert.currency_id.round(cur * cert.retention_percent / 100.0) if cert.currency_id else 0.0
            recovery = 0.0
            if cert.advance_recovery_percent and cur > 0:
                balance = cert._advance_balance_before()
                recovery = min(cur * cert.advance_recovery_percent / 100.0, max(balance, 0.0))
                recovery = cert.currency_id.round(recovery)
            deductions = sum(cert.deduction_ids.mapped('amount'))
            cert.amount_previous = prev
            cert.amount_current = cur
            cert.amount_cumulative = cum
            cert.retention_amount = retention
            cert.advance_recovery_amount = recovery
            cert.deduction_amount = deductions
            cert.amount_due = cur - retention - recovery - deductions
            value = cert.contract_id.amount_untaxed
            cert.progress_percent = cum / value * 100.0 if value else 0.0

    def _advance_balance_before(self):
        """Advance still to recover before this certificate."""
        self.ensure_one()
        contract = self.contract_id
        if not contract:
            return 0.0
        others = contract.certificate_ids.filtered(
            lambda c: c.state != 'cancel' and c != self and c._origin != self._origin
            and (not self.number or not c.number or c.number < self.number))
        recovered = sum(others.mapped('advance_recovery_amount'))
        return contract.advance_amount - recovered

    # ------------------------------------------------------------------
    @api.model_create_multi
    def create(self, vals_list):
        for vals in vals_list:
            contract = self.env['dvz.contract'].browse(vals.get('contract_id'))
            if vals.get('name', _('New')) == _('New'):
                vals['name'] = self.env['ir.sequence'].with_company(contract.company_id or self.env.company).next_by_code(
                    self._dvz_sequence_code(contract)) or _('New')
            if contract:
                vals.setdefault('number', len(contract.certificate_ids.filtered(lambda c: c.state != 'cancel')) + 1)
                vals.setdefault('retention_percent', contract.retention_percent)
                vals.setdefault('advance_recovery_percent', contract.advance_recovery_percent)
        certs = super().create(vals_list)
        for cert in certs:
            if not cert.line_ids:
                cert._load_boq_lines()
        return certs

    @api.model
    def _dvz_sequence_code(self, contract):
        return 'dvz.contract.certificate'

    def unlink(self):
        if any(c.state not in ('draft', 'cancel') for c in self):
            raise UserError(_('Only draft or cancelled certificates can be deleted.'))
        return super().unlink()

    @api.onchange('contract_id')
    def _onchange_contract_id(self):
        if self.contract_id:
            self.retention_percent = self.contract_id.retention_percent
            self.advance_recovery_percent = self.contract_id.advance_recovery_percent

    # ------------------------------------------------------------------
    def _previous_quantities(self):
        """Quantity certified per BOQ line on earlier, non-cancelled certificates."""
        self.ensure_one()
        domain = [
            ('certificate_id.contract_id', '=', self.contract_id.id),
            ('certificate_id.state', '!=', 'cancel'),
            ('contract_line_id', '!=', False),
        ]
        if self.id:
            domain.append(('certificate_id', '!=', self.id))
            if self.number:
                domain.append(('certificate_id.number', '<', self.number))
        result = {}
        for line in self.env['dvz.contract.certificate.line'].search(domain):
            result[line.contract_line_id.id] = result.get(line.contract_line_id.id, 0.0) + line.qty_current
        return result

    def _load_boq_lines(self):
        for cert in self:
            previous = cert._previous_quantities()
            existing = {l.contract_line_id.id: l for l in cert.line_ids if l.contract_line_id}
            commands = []
            for boq in cert.contract_id.line_ids.sorted(lambda l: (l.sequence, l.id)):
                if boq.id in existing:
                    commands.append((1, existing[boq.id].id, {'qty_previous': previous.get(boq.id, 0.0)}))
                    continue
                commands.append((0, 0, {
                    'contract_line_id': boq.id,
                    'sequence': boq.sequence,
                    'display_type': boq.display_type,
                    'item_no': boq.item_no,
                    'name': boq.name,
                    'uom_id': boq.uom_id.id,
                    'qty_contract': boq.quantity,
                    'price_unit': boq.price_unit,
                    'qty_previous': previous.get(boq.id, 0.0),
                }))
            if commands:
                cert.write({'line_ids': commands})

    def action_reload_lines(self):
        for cert in self:
            if cert.state != 'draft':
                raise UserError(_('Lines can only be reloaded on draft certificates.'))
            cert._load_boq_lines()
        return True

    # ------------------------------------------------------------------
    def _check_ready(self):
        for cert in self:
            if float_is_zero(cert.amount_current, precision_rounding=cert.currency_id.rounding or 0.01) \
                    and not cert.deduction_ids:
                raise UserError(_('Certificate %s has no progress this period.', cert.name))

    def action_submit(self):
        self._check_ready()
        for cert in self:
            if cert.state != 'draft':
                continue
            if cert.company_id.dvz_ipc_approval:
                cert.state = 'submitted'
                cert._notify_approvers()
            else:
                cert._do_approve()
        return True

    def _notify_approvers(self):
        for cert in self:
            manager = cert.contract_id.user_id
            if manager:
                cert.activity_schedule(
                    'mail.mail_activity_data_todo', user_id=manager.id,
                    summary=_('Approve payment certificate %s', cert.name))

    def _do_approve(self):
        self.write({'state': 'approved', 'approved_by_id': self.env.user.id,
                    'approved_date': fields.Date.context_today(self)})
        self.activity_feedback(['mail.mail_activity_data_todo'])

    def action_approve(self):
        if not self.env.user.has_group('dvz_contract.group_dvz_contract_manager'):
            raise UserError(_('Only contracting managers can approve certificates.'))
        for cert in self.filtered(lambda c: c.state == 'submitted'):
            cert._do_approve()
        return True

    def action_draft(self):
        for cert in self:
            if cert.invoice_id and cert.invoice_id.state != 'cancel':
                raise UserError(_('Cancel the invoice of %s first.', cert.name))
        self.write({'state': 'draft', 'approved_by_id': False, 'approved_date': False})
        return True

    def action_cancel(self):
        for cert in self:
            if cert.invoice_id and cert.invoice_id.state == 'posted':
                raise UserError(_('The invoice of %s is posted. Reverse it with a credit note first.', cert.name))
            if cert.invoice_id and cert.invoice_id.state == 'draft':
                cert.invoice_id.button_cancel()
        self.write({'state': 'cancel'})
        return True

    # ------------------------------------------------------------------
    # Invoicing (overridable for subcontracts)
    # ------------------------------------------------------------------
    def _dvz_move_type(self):
        return 'out_invoice'

    def _dvz_journal(self):
        self.ensure_one()
        journal = self.company_id.dvz_ipc_journal_id
        if not journal:
            journal = self.env['account.journal'].search([
                ('company_id', '=', self.company_id.id), ('type', '=', 'sale')], limit=1)
        if not journal:
            raise UserError(_('Set a sales journal in Settings > Contracting.'))
        return journal

    def _dvz_accounts(self):
        """Return the product and accounts used on the invoice lines."""
        self.ensure_one()
        company = self.company_id
        return {
            'product': company.dvz_ipc_product_id,
            'work': company.dvz_ipc_revenue_account_id,
            'retention': company.dvz_retention_account_id,
            'advance': company.dvz_advance_account_id,
            'deduction': company.dvz_deduction_account_id,
            'retention_method': company.dvz_retention_method,
            'recovery_tax': company.dvz_recovery_tax,
        }

    def _dvz_taxes(self):
        return self.contract_id.tax_ids

    def _dvz_analytic_distribution(self):
        analytic = self.contract_id.analytic_account_id
        return {str(analytic.id): 100.0} if analytic else False

    def _dvz_partner(self):
        return self.contract_id.partner_id

    def _prepare_invoice_lines(self):
        self.ensure_one()
        acc = self._dvz_accounts()
        taxes = self._dvz_taxes()
        analytic = self._dvz_analytic_distribution()
        product = acc['product']
        lines = []

        def base_line(name, quantity, price_unit, account=None, tax_ids=None, with_product=True, with_analytic=True):
            vals = {
                'name': name,
                'quantity': quantity,
                'price_unit': price_unit,
                'tax_ids': [(6, 0, (tax_ids if tax_ids is not None else taxes).ids)],
            }
            if with_product and product:
                vals['product_id'] = product.id
            if account:
                vals['account_id'] = account.id
            if with_analytic and analytic:
                vals['analytic_distribution'] = analytic
            return vals

        period = ''
        if self.period_start and self.period_end:
            period = ' (%s - %s)' % (self.period_start, self.period_end)
        if self.company_id.dvz_ipc_invoice_layout == 'detailed':
            for line in self.line_ids.filtered(lambda l: not l.display_type and l.qty_current):
                label = '%s %s' % (line.item_no or '', line.name or '')
                lines.append(base_line(label.strip(), line.qty_current, line.price_unit, acc['work']))
        else:
            lines.append(base_line(
                _('Work done - %(cert)s, certificate no. %(no)s%(period)s, contract %(contract)s',
                  cert=self.name, no=self.number, period=period, contract=self.contract_id.name),
                1.0, self.amount_current, acc['work']))

        if self.advance_recovery_amount:
            if not acc['advance']:
                raise UserError(_('Set the advance account in Settings > Contracting.'))
            lines.append(base_line(
                _('Advance recovery (%s%%)', self.advance_recovery_percent), 1.0, -self.advance_recovery_amount,
                acc['advance'], tax_ids=taxes if acc['recovery_tax'] else self.env['account.tax'],
                with_product=False))

        if self.retention_amount and acc['retention_method'] == 'deduct':
            if not acc['retention']:
                raise UserError(_('Set the retention account in Settings > Contracting.'))
            lines.append(base_line(
                _('Retention (%s%%)', self.retention_percent), 1.0, -self.retention_amount,
                acc['retention'], tax_ids=self.env['account.tax'], with_product=False, with_analytic=False))

        for ded in self.deduction_ids:
            account = ded.account_id or acc['deduction']
            if not account:
                raise UserError(_('Set the deductions account in Settings > Contracting.'))
            lines.append(base_line(
                '%s%s' % (ded.name, ded.reason and ' - %s' % ded.reason or ''), 1.0, -ded.amount,
                account, tax_ids=self.env['account.tax'], with_product=False))
        return lines

    def _prepare_invoice_vals(self):
        self.ensure_one()
        return {
            'move_type': self._dvz_move_type(),
            'partner_id': self._dvz_partner().id,
            'journal_id': self._dvz_journal().id,
            'currency_id': self.currency_id.id,
            'company_id': self.company_id.id,
            'invoice_date': self.date,
            'ref': '%s - %s' % (self.contract_id.name, self.name),
            'invoice_origin': self.contract_id.name,
            'dvz_contract_id': self.contract_id.id,
            'dvz_certificate_id': self.id,
            'dvz_move_kind': 'certificate',
            'invoice_line_ids': [(0, 0, vals) for vals in self._prepare_invoice_lines()],
        }

    def action_create_invoice(self):
        moves = self.env['account.move']
        for cert in self:
            if cert.state != 'approved':
                raise UserError(_('Only approved certificates can be invoiced.'))
            if cert.invoice_id and cert.invoice_id.state != 'cancel':
                raise UserError(_('Certificate %s is already invoiced.', cert.name))
            move = self.env['account.move'].with_company(cert.company_id).create(cert._prepare_invoice_vals())
            if cert.company_id.dvz_ipc_auto_post:
                move.action_post()
            cert.write({'invoice_id': move.id, 'state': 'invoiced'})
            moves |= move
        if len(moves) == 1:
            return moves._get_records_action() if hasattr(moves, '_get_records_action') else {
                'type': 'ir.actions.act_window', 'res_model': 'account.move', 'res_id': moves.id, 'view_mode': 'form'}
        return True

    def action_view_invoice(self):
        self.ensure_one()
        return {
            'type': 'ir.actions.act_window',
            'res_model': 'account.move',
            'res_id': self.invoice_id.id,
            'view_mode': 'form',
        }


class DvzContractCertificateLine(models.Model):
    _name = 'dvz.contract.certificate.line'
    _description = 'Payment Certificate Line'
    _order = 'certificate_id, sequence, id'

    certificate_id = fields.Many2one('dvz.contract.certificate', required=True, ondelete='cascade', index=True)
    contract_line_id = fields.Many2one('dvz.contract.line', 'BOQ Item', ondelete='restrict', index=True)
    company_id = fields.Many2one(related='certificate_id.company_id', store=True)
    currency_id = fields.Many2one(related='certificate_id.currency_id', store=True)
    state = fields.Selection(related='certificate_id.state')
    sequence = fields.Integer(default=10)
    display_type = fields.Selection([('line_section', 'Section'), ('line_note', 'Note')], default=False)
    item_no = fields.Char('Item No.')
    name = fields.Text('Description')
    uom_id = fields.Many2one('uom.uom', 'Unit')
    qty_contract = fields.Float('BOQ Qty', digits='Product Unit')
    price_unit = fields.Monetary('Rate')
    qty_previous = fields.Float('Previous Qty', digits='Product Unit')
    qty_current = fields.Float('This Period Qty', digits='Product Unit')
    qty_cumulative = fields.Float('Cumulative Qty', digits='Product Unit', compute='_compute_cumulative', store=True)
    percent_cumulative = fields.Float(
        'Cumulative %', compute='_compute_cumulative', inverse='_inverse_percent_cumulative', store=True)
    amount_previous = fields.Monetary('Previous Amount', compute='_compute_cumulative', store=True)
    amount_current = fields.Monetary('This Period Amount', compute='_compute_cumulative', store=True)
    amount_cumulative = fields.Monetary('Cumulative Amount', compute='_compute_cumulative', store=True)

    @api.depends('qty_previous', 'qty_current', 'qty_contract', 'price_unit', 'display_type')
    def _compute_cumulative(self):
        for line in self:
            if line.display_type:
                line.update({'qty_cumulative': 0.0, 'percent_cumulative': 0.0, 'amount_previous': 0.0,
                             'amount_current': 0.0, 'amount_cumulative': 0.0})
                continue
            cum = line.qty_previous + line.qty_current
            line.qty_cumulative = cum
            line.percent_cumulative = cum / line.qty_contract * 100.0 if line.qty_contract else 0.0
            line.amount_previous = line.qty_previous * line.price_unit
            line.amount_current = line.qty_current * line.price_unit
            line.amount_cumulative = cum * line.price_unit

    def _inverse_percent_cumulative(self):
        for line in self:
            if line.display_type or not line.qty_contract:
                continue
            target = line.qty_contract * line.percent_cumulative / 100.0
            line.qty_current = target - line.qty_previous

    @api.constrains('qty_current', 'qty_previous', 'qty_contract')
    def _check_overrun(self):
        for line in self:
            if line.display_type or line.company_id.dvz_allow_overrun or self.env.context.get('dvz_allow_overrun'):
                continue
            rounding = line.contract_line_id.uom_id.rounding if line.contract_line_id.uom_id else 0.0001
            if float_compare(line.qty_cumulative, line.qty_contract, precision_rounding=rounding or 0.0001) > 0:
                raise ValidationError(_(
                    'Item %(item)s: cumulative quantity %(cum)s is above the BOQ quantity %(boq)s.',
                    item=line.item_no or line.name, cum=line.qty_cumulative, boq=line.qty_contract))
            if float_compare(line.qty_cumulative, 0.0, precision_rounding=rounding or 0.0001) < 0:
                raise ValidationError(_('Item %s: cumulative quantity cannot be negative.', line.item_no or line.name))


class DvzContractCertificateDeduction(models.Model):
    _name = 'dvz.contract.certificate.deduction'
    _description = 'Payment Certificate Deduction'

    certificate_id = fields.Many2one('dvz.contract.certificate', required=True, ondelete='cascade', index=True)
    company_id = fields.Many2one(related='certificate_id.company_id', store=True)
    currency_id = fields.Many2one(related='certificate_id.currency_id', store=True)
    name = fields.Char('Deduction', required=True)
    deduction_type = fields.Selection(
        [('backcharge', 'Back-charge'), ('penalty', 'Penalty'), ('other', 'Other')],
        string='Type', default='backcharge', required=True)
    reason = fields.Char('Reason')
    amount = fields.Monetary('Amount', required=True)
    account_id = fields.Many2one('account.account', 'Account')
