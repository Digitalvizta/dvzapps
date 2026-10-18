from collections import defaultdict

from markupsafe import Markup, escape

from odoo import _, api, fields, models

from .cost_types import COST_TYPES, DIRECT_TYPES


class DvzContract(models.Model):
    _inherit = 'dvz.contract'

    costing_method = fields.Selection([
        ('auto', 'Remaining work at budget rates'),
        ('budget', 'Remaining budget'),
        ('manual', 'Entered by the project team'),
    ], string='Cost to Complete Method', default=lambda self: self.env.company.dvz_costing_method or 'auto',
        help='Remaining work at budget rates: budget × (1 − certified progress) for every BOQ item.\n'
             'Remaining budget: budget − actual cost.\n'
             'Entered by the project team: the cost to complete typed on each BOQ item.\n'
             'Open purchase orders are always included.')
    ho_overhead_percent = fields.Float(
        'Head-Office Overhead %', default=lambda self: self.env.company.dvz_ho_overhead_percent,
        help='Added on top of the direct cost when forecasting the final cost and margin.')
    jc_line_ids = fields.One2many('dvz.contract.line', 'contract_id', 'Job Costing',
                                  domain=[('display_type', '=', False)])

    jc_budget = fields.Monetary('Total Budget', compute='_compute_job_costing')
    jc_actual = fields.Monetary('Actual to Date', compute='_compute_job_costing')
    jc_open_commit = fields.Monetary('Committed (open POs)', compute='_compute_job_costing')
    jc_etc = fields.Monetary('Cost to Complete', compute='_compute_job_costing')
    jc_eac = fields.Monetary('Forecast Final Cost', compute='_compute_job_costing')
    jc_variance = fields.Monetary('Variance', compute='_compute_job_costing')
    jc_margin = fields.Monetary('Forecast Margin', compute='_compute_job_costing')
    jc_margin_percent = fields.Float('Forecast Margin %', compute='_compute_job_costing')
    jc_progress = fields.Float('Work Done %', compute='_compute_job_costing',
                               help='Certified progress weighted by BOQ value.')
    jc_cost_percent = fields.Float('Cost Spent %', compute='_compute_job_costing',
                                   help='Actual cost as a share of the forecast final cost.')
    jc_unlinked_actual = fields.Monetary('Costs not on a BOQ item', compute='_compute_job_costing')
    jc_summary_html = fields.Html('Cost Summary', compute='_compute_job_costing', sanitize=False)
    jc_alert_count = fields.Integer('Items over budget', compute='_compute_job_costing')

    def _compute_cost_control(self):
        super()._compute_cost_control()
        AnalyticLine = self.env['account.analytic.line'].sudo()
        for rec in self.filtered('id'):
            cost = -sum(AnalyticLine.search([('dvz_contract_id', '=', rec.id),
                                             ('dvz_cost_type', '!=', False)]).mapped('amount'))
            rec.actual_cost = cost
            rec.forecast_cost = cost + rec.committed_cost
            rec.budget_remaining = rec.cost_budget - cost - rec.committed_cost if rec.cost_budget else 0.0

    # ------------------------------------------------------------------
    def _jc_contract_actuals(self):
        """{cost_type: cost} for everything on the contract, and the part not linked to a BOQ item."""
        self.ensure_one()
        total, unlinked = defaultdict(float), defaultdict(float)
        if not self.id:
            return total, unlinked
        groups = self.env['account.analytic.line'].sudo()._read_group(
            [('dvz_contract_id', '=', self.id), ('dvz_cost_type', '!=', False)],
            ['dvz_cost_type', 'dvz_contract_line_id'], ['amount:sum'])
        for ctype, boq, amount in groups:
            total[ctype] += -amount
            if not boq:
                unlinked[ctype] += -amount
        return total, unlinked

    def _jc_data(self):
        """Everything the job costing tab and the PDF need, per cost type."""
        self.ensure_one()
        lines = self.line_ids.filtered(lambda l: not l.display_type)
        per_line = lines._jc_values()
        budget, etc = defaultdict(float), defaultdict(float)
        for v in per_line.values():
            for ctype, amount in v['budget'].items():
                budget[ctype] += amount
            for ctype, amount in v['etc'].items():
                etc[ctype] += amount
        actual, unlinked = self._jc_contract_actuals()
        direct_budget = sum(budget[t] for t in DIRECT_TYPES)
        pct = (self.ho_overhead_percent or 0.0) / 100.0
        budget['ho_overhead'] = direct_budget * pct
        direct_eac = sum(actual[t] for t in DIRECT_TYPES) + sum(etc[t] for t in DIRECT_TYPES)
        ho_forecast = max(direct_eac * pct, actual['ho_overhead'])
        etc['ho_overhead'] = max(ho_forecast - actual['ho_overhead'], 0.0)
        rows = []
        for ctype, label in COST_TYPES:
            b, a, e = budget[ctype], actual[ctype], etc[ctype]
            if not (b or a or e):
                continue
            rows.append({'type': ctype, 'label': label, 'budget': b, 'actual': a, 'etc': e,
                         'eac': a + e, 'variance': b - (a + e)})
        value = self.amount_untaxed
        weighted = sum(per_line[l.id]['progress'] * l.price_subtotal for l in lines if l.id in per_line)
        tot = {k: sum(r[k] for r in rows) for k in ('budget', 'actual', 'etc', 'eac', 'variance')}
        return {
            'rows': rows, 'total': tot, 'per_line': per_line,
            'open_commit': sum(v['open_commit'] for v in per_line.values()),
            'progress': weighted / value if value else 0.0,
            'unlinked': sum(unlinked.values()),
            'margin': value - tot['eac'],
        }

    def _jc_html(self, data):
        cur = self.currency_id

        def money(v):
            return escape(cur.format(v)) if cur else escape('%.2f' % v)

        head = Markup(''.join('<th class="text-end">%s</th>' % escape(h) for h in (
            _('Budget'), _('Actual'), _('Cost to Complete'), _('Forecast Final'), _('Variance'))))
        body = Markup()
        for r in data['rows']:
            cls = 'text-danger' if r['variance'] < -0.005 else 'text-success' if r['variance'] > 0.005 else ''
            body += Markup('<tr><td>%s</td><td class="text-end">%s</td><td class="text-end">%s</td>'
                           '<td class="text-end">%s</td><td class="text-end"><b>%s</b></td>'
                           '<td class="text-end %s">%s</td></tr>') % (
                r['label'], money(r['budget']), money(r['actual']), money(r['etc']), money(r['eac']),
                cls, money(r['variance']))
        t = data['total']
        cls = 'text-danger' if t['variance'] < -0.005 else 'text-success'
        foot = Markup('<tr class="fw-bold border-top"><td>%s</td><td class="text-end">%s</td>'
                      '<td class="text-end">%s</td><td class="text-end">%s</td><td class="text-end">%s</td>'
                      '<td class="text-end %s">%s</td></tr>') % (
            _('Total'), money(t['budget']), money(t['actual']), money(t['etc']), money(t['eac']), cls,
            money(t['variance']))
        if not data['rows']:
            body = Markup('<tr><td colspan="6" class="text-muted">%s</td></tr>') % _(
                'No budget or cost yet. Enter the cost split on the BOQ items below, then post bills, timesheets or site diaries on this contract.')
        return Markup('<table class="table table-sm o_dvz_jc_table mb-0"><thead><tr><th>%s</th>%s</tr></thead>'
                      '<tbody>%s</tbody><tfoot>%s</tfoot></table>') % (_('Cost type'), head, body, foot)

    @api.depends('line_ids', 'ho_overhead_percent', 'costing_method')
    def _compute_job_costing(self):
        for rec in self:
            if not rec.id:
                rec.update({f: 0.0 for f in ('jc_budget', 'jc_actual', 'jc_open_commit', 'jc_etc', 'jc_eac',
                                             'jc_variance', 'jc_margin', 'jc_margin_percent', 'jc_progress',
                                             'jc_cost_percent', 'jc_unlinked_actual')})
                rec.jc_summary_html = False
                rec.jc_alert_count = 0
                continue
            data = rec._jc_data()
            t = data['total']
            rec.jc_budget = t['budget']
            rec.jc_actual = t['actual']
            rec.jc_open_commit = data['open_commit']
            rec.jc_etc = t['etc']
            rec.jc_eac = t['eac']
            rec.jc_variance = t['variance']
            rec.jc_margin = data['margin']
            rec.jc_margin_percent = data['margin'] / rec.amount_untaxed * 100.0 if rec.amount_untaxed else 0.0
            rec.jc_progress = data['progress'] * 100.0
            rec.jc_cost_percent = t['actual'] / t['eac'] * 100.0 if t['eac'] else 0.0
            rec.jc_unlinked_actual = data['unlinked']
            rec.jc_summary_html = rec._jc_html(data)
            rec.jc_alert_count = sum(
                1 for l in rec.line_ids
                if not l.display_type and l.id in data['per_line'] and (l.cost_subtotal or 0.0)
                and l.cost_subtotal - data['per_line'][l.id]['eac_total'] < -0.005)

    # ------------------------------------------------------------------
    def action_view_job_cost_report(self):
        self.ensure_one()
        return {
            'type': 'ir.actions.act_window',
            'name': _('Job Cost Analysis: %s', self.name),
            'res_model': 'dvz.job.cost.report',
            'view_mode': 'pivot,list,graph',
            'domain': [('contract_id', '=', self.id)],
            'context': {'search_default_group_cost_type': 1},
        }

    def action_view_jc_costs(self):
        self.ensure_one()
        return {
            'type': 'ir.actions.act_window',
            'name': _('Contract Costs: %s', self.name),
            'res_model': 'account.analytic.line',
            'view_mode': 'list,pivot,graph,form',
            'domain': [('dvz_contract_id', '=', self.id), ('dvz_cost_type', '!=', False)],
            'context': {'search_default_group_dvz_cost_type': 1, 'create': False},
        }

    def action_jc_reclassify(self):
        self.ensure_one()
        lines = self.env['account.analytic.line'].search(
            [('dvz_contract_id', '=', self.id)] if not self.analytic_account_id else
            ['|', ('dvz_contract_id', '=', self.id), ('auto_account_id', '=', self.analytic_account_id.id)])
        lines |= self.env['account.analytic.line'].search([(self._analytic_column() or 'account_id', '=',
                                                             self.analytic_account_id.id)]) \
            if self.analytic_account_id else self.env['account.analytic.line']
        lines._dvz_classify()
        return {
            'type': 'ir.actions.client', 'tag': 'display_notification',
            'params': {'message': _('Costs updated: %s lines checked.', len(lines)), 'type': 'success',
                       'next': {'type': 'ir.actions.client', 'tag': 'soft_reload'}},
        }
