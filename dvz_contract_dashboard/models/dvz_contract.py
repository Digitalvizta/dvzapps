from datetime import date as Date, timedelta

from dateutil.relativedelta import relativedelta

from odoo import _, api, fields, models


class DvzContract(models.Model):
    _inherit = 'dvz.contract'

    @api.model
    def _dvz_short(self, amount, currency):
        """Compact amount for cards: SAR 4.49M, SAR 812K."""
        value = abs(amount)
        sign = '-' if amount < 0 else ''
        if value >= 1_000_000:
            text = '%.2fM' % (value / 1_000_000)
        elif value >= 10_000:
            text = '%.0fK' % (value / 1_000)
        else:
            text = '{:,.0f}'.format(value)
        symbol = currency.symbol or currency.name
        if currency.position == 'after':
            return '%s%s %s' % (sign, text, symbol)
        return '%s%s %s' % (sign, symbol, text)

    @api.model
    def get_dvz_dashboard_data(self):
        company = self.env.company
        currency = company.currency_id
        company_ids = self.env.companies.ids
        today = fields.Date.context_today(self)

        def conv(amount, from_currency, record_company=None):
            if not amount or not from_currency or from_currency == currency:
                return amount or 0.0
            return from_currency._convert(amount, currency, record_company or company, today)

        def money(amount):
            return {'value': amount, 'short': self._dvz_short(amount, currency), 'full': currency.format(amount)}

        contracts = self.search([
            ('company_id', 'in', company_ids), ('contract_type', '=', 'client'),
            ('state', 'in', ('progress', 'handover'))])

        value = certified = retention = advance = budget = actual = committed = 0.0
        rows = []
        for c in contracts:
            cv = conv(c.amount_untaxed, c.currency_id, c.company_id)
            value += cv
            certified += conv(c.certified_amount, c.currency_id, c.company_id)
            retention += conv(max(c.retention_balance, 0.0), c.currency_id, c.company_id)
            advance += conv(max(c.advance_balance, 0.0), c.currency_id, c.company_id)
            budget += conv(c.cost_budget, c.currency_id, c.company_id)
            actual += conv(c.actual_cost, c.currency_id, c.company_id)
            committed += conv(c.committed_cost, c.currency_id, c.company_id)
            forecast_cost = max(c.cost_budget, c.forecast_cost)
            forecast_margin = (c.amount_untaxed - forecast_cost) / c.amount_untaxed * 100.0 \
                if c.amount_untaxed and c.cost_budget else 0.0
            rows.append({
                'id': c.id,
                'name': c.name,
                'title': c.title or '',
                'client': c.partner_id.display_name,
                'state': dict(c._fields['state'].selection).get(c.state),
                'state_key': c.state,
                'value': money(cv),
                'certified_percent': round(c.certified_percent, 1),
                'cost_used_percent': round(c.forecast_cost / c.cost_budget * 100.0, 1) if c.cost_budget else 0.0,
                'planned_margin': round(c.planned_margin_percent, 1),
                'forecast_margin': round(forecast_margin, 1),
                'retention': money(conv(max(c.retention_balance, 0.0), c.currency_id, c.company_id)),
                'over_budget': c.over_budget_count,
                'end': c.date_end and fields.Date.to_string(c.date_end) or '',
                'late': bool(c.state == 'progress' and c.date_end and c.date_end < today),
            })
        rows.sort(key=lambda r: -r['value']['value'])

        # receivables
        # sudo: contracting users are not necessarily invoicing users (no ACL on account.move)
        Move = self.env['account.move'].sudo()
        inv_domain = [('dvz_contract_id', 'in', contracts.ids), ('move_type', 'in', ('out_invoice', 'out_refund')),
                      ('state', '=', 'posted'), ('amount_residual', '!=', 0)]
        invoices = Move.search(inv_domain)
        receivable = sum(invoices.mapped('amount_residual_signed'))
        overdue_moves = invoices.filtered(lambda m: m.invoice_date_due and m.invoice_date_due < today)
        overdue = sum(overdue_moves.mapped('amount_residual_signed'))

        # approvals
        Cert = self.env['dvz.contract.certificate']
        Var = self.env['dvz.contract.variation']
        MR = self.env['dvz.material.request']
        approvals = [
            {'label': _('Payment certificates'), 'count': Cert.search_count([('company_id', 'in', company_ids), ('state', '=', 'submitted')]),
             'model': 'dvz.contract.certificate', 'domain': [('state', '=', 'submitted')], 'icon': 'fa-file-text-o'},
            {'label': _('Variation orders'), 'count': Var.search_count([('company_id', 'in', company_ids), ('state', '=', 'submitted')]),
             'model': 'dvz.contract.variation', 'domain': [('state', '=', 'submitted')], 'icon': 'fa-random'},
            {'label': _('Material requests'), 'count': MR.search_count([('company_id', 'in', company_ids), ('state', '=', 'submitted')]),
             'model': 'dvz.material.request', 'domain': [('state', '=', 'submitted')], 'icon': 'fa-truck'},
            {'label': _('Certificates to invoice'), 'count': Cert.search_count([('company_id', 'in', company_ids), ('state', '=', 'approved')]),
             'model': 'dvz.contract.certificate', 'domain': [('state', '=', 'approved')], 'icon': 'fa-money'},
        ]

        # guarantees
        Guarantee = self.env['dvz.bank.guarantee']
        reminder = company.dvz_guarantee_reminder_days or 30
        active_g = Guarantee.search([('company_id', 'in', company_ids), ('state', '=', 'active')], order='expiry_date')
        given = active_g.filtered(lambda g: g.direction == 'given')
        attention = active_g.filtered(lambda g: g.expiry_date and g.expiry_date <= today + timedelta(days=reminder))
        guarantees = [{
            'id': g.id,
            'name': g.name,
            'type': dict(g._fields['guarantee_type'].selection).get(g.guarantee_type),
            'partner': g.partner_id.display_name or '',
            'amount': money(conv(g.amount, g.currency_id, g.company_id)),
            'expiry': fields.Date.to_string(g.expiry_date),
            'days': (g.expiry_date - today).days,
        } for g in attention[:8]]

        # billing per month (last 6 months, approved and invoiced certificates of client contracts)
        start = Date(today.year, today.month, 1) - relativedelta(months=5)
        certs = Cert.search([('company_id', 'in', company_ids), ('contract_type', '=', 'client'),
                             ('state', 'in', ('approved', 'invoiced')), ('date', '>=', start)])
        billing = []
        for i in range(6):
            month = start + relativedelta(months=i)
            nxt = month + relativedelta(months=1)
            amount = sum(conv(c.amount_current, c.currency_id, c.company_id)
                         for c in certs if month <= c.date < nxt)
            billing.append({'label': month.strftime('%b'), 'amount': amount, 'short': self._dvz_short(amount, currency)})

        # cash flow forecast
        Cash = self.env['dvz.cashflow.line']
        for comp in self.env.companies:
            Cash._rebuild(comp)
        cashflow = Cash.get_monthly_summary(6)
        for month in cashflow:
            month['in_short'] = self._dvz_short(month['cash_in'], currency)
            month['out_short'] = self._dvz_short(month['cash_out'], currency)
            month['net_short'] = self._dvz_short(month['net'], currency)
            month['cumulative_short'] = self._dvz_short(month['cumulative'], currency)

        over_budget_items = self.env['dvz.contract.line'].search_count([
            ('contract_id', 'in', contracts.ids), ('over_budget', '=', True)])
        planned_margin = (value - budget) / value * 100.0 if value and budget else 0.0
        forecast_cost_total = max(budget, actual + committed)
        forecast_margin = (value - forecast_cost_total) / value * 100.0 if value and budget else 0.0

        return {
            'company': company.name,
            'today': fields.Date.to_string(today),
            'kpi': {
                'active': len(contracts),
                'value': money(value),
                'certified': money(certified),
                'certified_percent': round(certified / value * 100.0, 1) if value else 0.0,
                'receivable': money(receivable),
                'overdue': money(overdue),
                'retention': money(retention),
                'advance': money(advance),
                'budget': money(budget),
                'actual': money(actual),
                'committed': money(committed),
                'cost_used_percent': round((actual + committed) / budget * 100.0, 1) if budget else 0.0,
                'planned_margin': round(planned_margin, 1),
                'forecast_margin': round(forecast_margin, 1),
                'over_budget_items': over_budget_items,
                'approvals': sum(a['count'] for a in approvals[:3]),
                'guarantees_given': money(sum(conv(g.amount, g.currency_id, g.company_id) for g in given)),
                'guarantees_attention': len(attention),
            },
            'domains': {
                'contracts': [('id', 'in', contracts.ids)],
                'receivable': [('id', 'in', invoices.ids)],
                'overdue': [('id', 'in', overdue_moves.ids)],
                'guarantees': [('id', 'in', attention.ids)],
            },
            'contracts': rows[:12],
            'approvals': approvals,
            'guarantees': guarantees,
            'billing': billing,
            'billing_max': max([b['amount'] for b in billing] + [0.0]),
            'cashflow': cashflow,
            'cashflow_max': max([max(m['cash_in'], m['cash_out']) for m in cashflow] + [0.0]),
        }
