from datetime import date as Date, timedelta

from dateutil.relativedelta import relativedelta

from odoo import _, api, fields, models

CATEGORIES = [
    ('receivable_open', 'Open client invoices'),
    ('ipc_pending', 'Certificates not yet invoiced'),
    ('billing_planned', 'Planned progress billing'),
    ('retention_release', 'Retention release'),
    ('payable_open', 'Open vendor bills'),
    ('subcontract_pending', 'Subcontractor certificates not billed'),
    ('subcontract_planned', 'Planned subcontractor payments'),
    ('purchase_open', 'Purchase orders not billed'),
    ('cost_planned', 'Other planned costs'),
]


class DvzCashflowLine(models.Model):
    _name = 'dvz.cashflow.line'
    _description = 'Contract Cash Flow Forecast'
    _order = 'date, contract_id, id'
    _rec_name = 'name'

    name = fields.Char('Source', required=True)
    company_id = fields.Many2one('res.company', required=True, index=True)
    currency_id = fields.Many2one(related='company_id.currency_id')
    contract_id = fields.Many2one('dvz.contract', 'Contract', index=True, ondelete='cascade')
    project_id = fields.Many2one('project.project', 'Project')
    partner_id = fields.Many2one('res.partner', 'Partner')
    date = fields.Date('Expected Date', required=True, index=True)
    flow = fields.Selection([('in', 'Cash In'), ('out', 'Cash Out')], required=True)
    category = fields.Selection(CATEGORIES, required=True)
    is_planned = fields.Boolean('Planned', help='Estimated from the contract plan, not from an existing document.')
    amount = fields.Monetary('Net Cash', help='Positive for cash in, negative for cash out.')
    amount_in = fields.Monetary('Cash In')
    amount_out = fields.Monetary('Cash Out')
    res_model = fields.Char('Document Model')
    res_id = fields.Integer('Document ID')

    # ------------------------------------------------------------------
    # Helpers
    # ------------------------------------------------------------------
    @api.model
    def _tax_factor(self, taxes):
        rate = sum(t.amount for t in taxes if t.amount_type == 'percent')
        return 1.0 + rate / 100.0

    @api.model
    def _months(self, start, end):
        """First day of every month between start and end (inclusive), at least one."""
        first = Date(start.year, start.month, 1)
        last = Date(end.year, end.month, 1) if end and end > start else first
        months = []
        current = first
        while current <= last and len(months) < 60:
            months.append(current)
            current += relativedelta(months=1)
        return months

    # ------------------------------------------------------------------
    # Build
    # ------------------------------------------------------------------
    @api.model
    def _cron_rebuild(self):
        for company in self.env['res.company'].sudo().search([]):
            self._rebuild(company)

    @api.model
    def _rebuild(self, company):
        self = self.sudo().with_company(company)  # noqa: PLW0642
        self.search([('company_id', '=', company.id)]).unlink()
        today = fields.Date.context_today(self)
        vals_list = []
        contracts = self.env['dvz.contract'].search([
            ('company_id', '=', company.id),
            ('contract_type', '=', 'client'),
            ('state', 'in', ('progress', 'handover')),
        ])
        for contract in contracts:
            vals_list += self._contract_lines(contract, today)
        self.create(vals_list)
        return True

    def _line(self, contract, category, when, amount, name, today, planned=False, partner=None, document=None,
              currency=None):
        company = contract.company_id
        currency = currency or contract.currency_id
        if currency and currency != company.currency_id:
            amount = currency._convert(amount, company.currency_id, company, today)
        amount = company.currency_id.round(amount)
        when = max(when or today, today)
        return {
            'name': name,
            'company_id': company.id,
            'contract_id': contract.id,
            'project_id': contract.project_id.id,
            'partner_id': (partner or contract.partner_id).id,
            'date': when,
            'flow': 'in' if amount >= 0 else 'out',
            'category': category,
            'is_planned': planned,
            'amount': amount,
            'amount_in': amount if amount > 0 else 0.0,
            'amount_out': -amount if amount < 0 else 0.0,
            'res_model': document and document._name,
            'res_id': document and document.id,
        }

    def _contract_lines(self, contract, today):
        company = contract.company_id
        client_days = company.dvz_cash_client_days or 0
        vendor_days = company.dvz_cash_vendor_days or 0
        Move = self.env['account.move']
        res = []
        skip_zero = lambda amount: company.currency_id.is_zero(amount)  # noqa: E731

        # ---------------- cash in: client invoices
        subs = contract.subcontract_ids.filtered(lambda s: s.state in ('progress', 'handover'))
        moves = Move.search([('dvz_contract_id', '=', contract.id),
                             ('move_type', 'in', ('out_invoice', 'out_refund')),
                             ('state', 'in', ('draft', 'posted'))])
        for move in moves:
            if move.state == 'posted':
                amount = move.amount_residual_signed
                when = move.invoice_date_due or move.invoice_date
            else:
                amount = move.amount_total_signed
                when = (move.invoice_date or today) + timedelta(days=client_days)
            if skip_zero(amount):
                continue
            res.append(self._line(contract, 'receivable_open', when, amount,
                                  move.name if move.name and move.name != '/' else _('Draft invoice'), today,
                                  document=move, currency=company.currency_id))

        # ---------------- cash in: certificates approved / submitted, not invoiced
        tax_factor = self._tax_factor(contract.tax_ids)
        pending = contract.certificate_ids.filtered(lambda c: c.state in ('submitted', 'approved') and not c.invoice_id)
        for cert in pending:
            amount = (cert.amount_current - cert.advance_recovery_amount - cert.deduction_amount) * tax_factor \
                - cert.retention_amount
            if skip_zero(amount):
                continue
            res.append(self._line(contract, 'ipc_pending', cert.date + timedelta(days=client_days), amount,
                                  cert.name, today, document=cert))

        # ---------------- cash in: planned billing of the remaining work
        open_certs = contract.certificate_ids.filtered(lambda c: c.state in ('draft', 'submitted'))
        remaining = max(contract.amount_to_certify - sum(open_certs.mapped('amount_current')), 0.0)
        retention_future = remaining * contract.retention_percent / 100.0
        if remaining and contract.state == 'progress':
            recovery = min(max(contract.advance_balance, 0.0), remaining * contract.advance_recovery_percent / 100.0)
            cash = (remaining - recovery) * tax_factor - retention_future
            start = today + relativedelta(months=1)
            end = max(contract.date_end or start, start)
            months = self._months(start, end)
            for month in months:
                when = month + relativedelta(day=25) + timedelta(days=client_days)
                res.append(self._line(contract, 'billing_planned', when, cash / len(months),
                                      _('Planned billing %s', month.strftime('%m/%Y')), today, planned=True))

        # ---------------- cash in: retention release
        balance = max(contract.retention_balance, 0.0)
        if contract.state == 'progress':
            total = balance + retention_future
            if total:
                end = max(contract.date_end or today, today)
                pct = company.dvz_release_handover_percent if company.dvz_release_at_handover else 0.0
                first = total * pct / 100.0
                if first:
                    res.append(self._line(contract, 'retention_release',
                                          end + relativedelta(months=1) + timedelta(days=client_days), first,
                                          _('Retention release at handover'), today, planned=True))
                if total - first:
                    res.append(self._line(contract, 'retention_release',
                                          end + relativedelta(months=contract.defects_months or 12) + timedelta(days=client_days),
                                          total - first, _('Retention release after defects period'), today, planned=True))
        elif balance:
            drafts = contract.release_ids.filtered(lambda r: r.state == 'draft')
            first = min(sum(drafts.mapped('amount')), balance)
            if first:
                res.append(self._line(contract, 'retention_release', today + timedelta(days=client_days), first,
                                      ', '.join(drafts.mapped('name')), today))
            if balance - first:
                res.append(self._line(contract, 'retention_release',
                                      (contract.dlp_end_date or today) + timedelta(days=client_days), balance - first,
                                      _('Retention release after defects period'), today, planned=True))

        # ---------------- cash out: vendor and subcontractor bills
        contract_ids = (contract | subs).ids
        bills = Move.search([('move_type', 'in', ('in_invoice', 'in_refund')),
                             ('state', 'in', ('draft', 'posted')),
                             '|', ('dvz_contract_id', 'in', contract_ids),
                             ('invoice_line_ids.purchase_line_id.order_id.dvz_contract_id', '=', contract.id)])
        for bill in bills:
            if bill.state == 'posted':
                amount = bill.amount_residual_signed
                when = bill.invoice_date_due or bill.invoice_date
            else:
                amount = bill.amount_total_signed
                when = (bill.invoice_date or today) + timedelta(days=vendor_days)
            if skip_zero(amount):
                continue
            res.append(self._line(contract, 'payable_open', when, amount,
                                  bill.name if bill.name and bill.name != '/' else _('Draft bill'), today,
                                  partner=bill.partner_id, document=bill, currency=company.currency_id))

        # ---------------- cash out: subcontractors
        subs_remaining_value = 0.0
        for sub in subs:
            sub_tax = self._tax_factor(sub.tax_ids)
            for cert in sub.certificate_ids.filtered(lambda c: c.state in ('submitted', 'approved') and not c.invoice_id):
                amount = (cert.amount_current - cert.advance_recovery_amount - cert.deduction_amount) * sub_tax \
                    - cert.retention_amount
                if not skip_zero(amount):
                    res.append(self._line(contract, 'subcontract_pending', cert.date + timedelta(days=vendor_days),
                                          -amount, cert.name, today, partner=sub.partner_id, document=cert,
                                          currency=sub.currency_id))
            open_sub = sub.certificate_ids.filtered(lambda c: c.state in ('draft', 'submitted'))
            sub_remaining = max(sub.amount_to_certify - sum(open_sub.mapped('amount_current')), 0.0)
            subs_remaining_value += sub_remaining
            sub_ret_future = sub_remaining * sub.retention_percent / 100.0
            if sub_remaining and sub.state == 'progress':
                cash = sub_remaining * sub_tax - sub_ret_future
                start = today + relativedelta(months=1)
                end = max(sub.date_end or contract.date_end or start, start)
                months = self._months(start, end)
                for month in months:
                    when = month + relativedelta(day=25) + timedelta(days=vendor_days)
                    res.append(self._line(contract, 'subcontract_planned', when, -cash / len(months),
                                          _('%(sub)s planned %(month)s', sub=sub.name, month=month.strftime('%m/%Y')),
                                          today, planned=True, partner=sub.partner_id, currency=sub.currency_id))
            sub_ret = max(sub.retention_balance, 0.0) + sub_ret_future
            if sub_ret:
                when = (contract.dlp_end_date or (contract.date_end or today) + relativedelta(
                    months=contract.defects_months or 12)) + timedelta(days=vendor_days)
                res.append(self._line(contract, 'subcontract_planned', when, -sub_ret,
                                      _('%s retention payable', sub.name), today, planned=True,
                                      partner=sub.partner_id, currency=sub.currency_id))

        # ---------------- cash out: purchase orders not billed
        pols = self.env['purchase.order.line'].search([
            ('order_id.dvz_contract_id', '=', contract.id), ('order_id.state', '=', 'purchase'),
            ('display_type', '=', False)])
        for pol in pols:
            open_qty = pol.product_qty - pol.qty_invoiced
            if open_qty <= 0 or not pol.product_qty:
                continue
            amount = pol.price_total / pol.product_qty * open_qty
            planned_date = fields.Date.to_date(pol.date_planned) if pol.date_planned else today
            res.append(self._line(contract, 'purchase_open', planned_date + timedelta(days=vendor_days), -amount,
                                  pol.order_id.name, today, partner=pol.order_id.partner_id, document=pol.order_id,
                                  currency=pol.currency_id))

        # ---------------- cash out: rest of the cost budget not yet committed
        if contract.state == 'progress' and contract.cost_budget:
            other = contract.cost_budget - contract.actual_cost - contract.committed_cost - subs_remaining_value
            if other > 0:
                purchase_tax = self._tax_factor(company.dvz_purchase_tax_ids)
                start = today + relativedelta(months=1)
                end = max(contract.date_end or start, start)
                months = self._months(start, end)
                for month in months:
                    when = month + relativedelta(day=15) + timedelta(days=vendor_days)
                    res.append(self._line(contract, 'cost_planned', when, -other * purchase_tax / len(months),
                                          _('Planned costs %s', month.strftime('%m/%Y')), today, planned=True))
        return res

    # ------------------------------------------------------------------
    # UI
    # ------------------------------------------------------------------
    @api.model
    def action_open_forecast(self):
        for company in self.env.companies:
            self._rebuild(company)
        action = self.env['ir.actions.act_window']._for_xml_id('dvz_contract_cashflow.action_dvz_cashflow_line')
        return action

    def action_open_document(self):
        self.ensure_one()
        if not self.res_model or not self.res_id:
            return False
        return {
            'type': 'ir.actions.act_window',
            'res_model': self.res_model,
            'res_id': self.res_id,
            'view_mode': 'form',
        }

    @api.model
    def get_monthly_summary(self, months=6):
        """Used by the contracting dashboard: cash in / out / net per month for the next N months."""
        today = fields.Date.context_today(self)
        start = Date(today.year, today.month, 1)
        result = []
        cumulative = 0.0
        for i in range(months):
            month = start + relativedelta(months=i)
            nxt = month + relativedelta(months=1)
            lines = self.search([('company_id', 'in', self.env.companies.ids), ('date', '>=', month), ('date', '<', nxt)])
            cash_in = sum(lines.mapped('amount_in'))
            cash_out = sum(lines.mapped('amount_out'))
            cumulative += cash_in - cash_out
            result.append({
                'label': month.strftime('%b %Y'),
                'cash_in': cash_in,
                'cash_out': cash_out,
                'net': cash_in - cash_out,
                'cumulative': cumulative,
            })
        return result
