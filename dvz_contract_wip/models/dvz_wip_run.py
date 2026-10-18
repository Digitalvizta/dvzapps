from datetime import timedelta

from odoo import _, api, fields, models
from odoo.exceptions import UserError

from .res_company import WIP_METHODS

# Direct cost only: head-office overheads do not measure progress and are not contract costs under IFRS 15.
NON_DIRECT = ('ho_overhead',)


class DvzWipRun(models.Model):
    _name = 'dvz.wip.run'
    _description = 'Month-end WIP Run (Revenue Recognition)'
    _inherit = ['mail.thread']
    _order = 'date desc, id desc'
    _check_company_auto = True

    name = fields.Char('Reference', required=True, copy=False, readonly=True, default=lambda self: _('New'))
    date = fields.Date('Period End', required=True, tracking=True,
                       default=lambda self: fields.Date.end_of(fields.Date.context_today(self), 'month')
                       if fields.Date.context_today(self).day > 25
                       else fields.Date.start_of(fields.Date.context_today(self), 'month') - timedelta(days=1))
    company_id = fields.Many2one('res.company', required=True, default=lambda self: self.env.company)
    currency_id = fields.Many2one(related='company_id.currency_id')
    journal_id = fields.Many2one('account.journal', 'Journal', check_company=True,
                                 domain="[('type', '=', 'general')]",
                                 default=lambda self: self.env.company.dvz_wip_journal_id)
    state = fields.Selection([('draft', 'Draft'), ('posted', 'Posted'), ('cancel', 'Cancelled')],
                             default='draft', required=True, tracking=True, copy=False)
    line_ids = fields.One2many('dvz.wip.line', 'run_id', 'Contracts', copy=False)
    move_id = fields.Many2one('account.move', 'Journal Entry', readonly=True, copy=False)
    reversal_move_id = fields.Many2one('account.move', 'Reversal Entry', readonly=True, copy=False)
    note = fields.Text('Notes')

    total_earned = fields.Monetary('Revenue Earned', compute='_compute_totals')
    total_billed = fields.Monetary('Billed', compute='_compute_totals')
    total_under = fields.Monetary('Under-billing (asset)', compute='_compute_totals')
    total_over = fields.Monetary('Over-billing (liability)', compute='_compute_totals')
    total_provision = fields.Monetary('Loss Provision', compute='_compute_totals')

    @api.depends('line_ids.earned', 'line_ids.billed', 'line_ids.adjustment', 'line_ids.loss_provision')
    def _compute_totals(self):
        for rec in self:
            rec.total_earned = sum(rec.line_ids.mapped('earned'))
            rec.total_billed = sum(rec.line_ids.mapped('billed'))
            rec.total_under = sum(a for a in rec.line_ids.mapped('adjustment') if a > 0)
            rec.total_over = -sum(a for a in rec.line_ids.mapped('adjustment') if a < 0)
            rec.total_provision = sum(rec.line_ids.mapped('loss_provision'))

    @api.model_create_multi
    def create(self, vals_list):
        for vals in vals_list:
            if vals.get('name', _('New')) == _('New'):
                vals['name'] = self.env['ir.sequence'].next_by_code('dvz.wip.run') or _('New')
        return super().create(vals_list)

    def unlink(self):
        if any(rec.state == 'posted' for rec in self):
            raise UserError(_('Cancel a posted WIP run before deleting it.'))
        return super().unlink()

    # ------------------------------------------------------------------
    def _contracts(self):
        self.ensure_one()
        return self.env['dvz.contract'].search([
            ('company_id', '=', self.company_id.id), ('contract_type', '=', 'client'),
            ('state', 'in', ('progress', 'handover')), ('date_start', '<=', self.date)])

    def action_compute(self):
        for rec in self:
            if rec.state != 'draft':
                raise UserError(_('Only draft WIP runs can be recalculated.'))
            manual = {l.contract_id.id: l.percent for l in rec.line_ids if l.method == 'manual'}
            lines = []
            for contract in rec._contracts():
                vals = rec._line_values(contract)
                if contract.id in manual:
                    vals['percent'] = manual[contract.id]
                lines.append((0, 0, vals))
            rec.line_ids = [(5, 0, 0)] + lines
        return True

    def _line_values(self, contract):
        self.ensure_one()
        end = self.date
        value = contract.amount_untaxed
        Analytic = self.env['account.analytic.line'].sudo()
        cost = -sum(Analytic.search([
            ('dvz_contract_id', '=', contract.id), ('date', '<=', end),
            ('dvz_cost_type', '!=', False), ('dvz_cost_type', 'not in', NON_DIRECT)]).mapped('amount'))
        data = contract._jc_data()
        eac = sum(r['eac'] for r in data['rows'] if r['type'] not in NON_DIRECT)
        eac = max(eac, cost)
        certs = contract.certificate_ids.filtered(
            lambda c: c.state in ('approved', 'invoiced') and c.date and c.date <= end)
        certified = max(certs.mapped('amount_cumulative') or [0.0])
        billed = sum(certs.filtered(lambda c: c.invoice_id and c.invoice_id.state == 'posted').mapped('amount_current'))
        method = contract.wip_method or 'cost'
        if contract.state == 'handover' or (contract.handover_date and contract.handover_date <= end):
            percent = 100.0          # handed over: the work is complete, all revenue is earned
        elif method == 'cost':
            percent = cost / eac * 100.0 if eac else 0.0
        elif method == 'certified':
            percent = certified / value * 100.0 if value else 0.0
        else:
            percent = contract.wip_percent_manual
        return {
            'contract_id': contract.id,
            'method': method,
            'contract_value': value,
            'cost_to_date': cost,
            'forecast_cost': eac,
            'certified': certified,
            'billed': billed,
            'percent': min(max(percent, 0.0), 100.0),
        }

    def _check_config(self):
        self.ensure_one()
        c = self.company_id
        missing = [label for label, acc in (
            (_('WIP journal'), self.journal_id),
            (_('contract revenue account'), c.dvz_wip_revenue_account_id),
            (_('contract asset account'), c.dvz_wip_asset_account_id),
            (_('contract liability account'), c.dvz_wip_liability_account_id)) if not acc]
        if any(l.loss_provision for l in self.line_ids):
            missing += [label for label, acc in (
                (_('expected loss expense account'), c.dvz_wip_loss_account_id),
                (_('loss provision account'), c.dvz_wip_provision_account_id)) if not acc]
        if missing:
            raise UserError(_('Set the %s in Contracting > Configuration > Settings > Revenue Recognition.',
                              ', '.join(missing)))

    def action_post(self):
        for rec in self:
            if rec.state != 'draft':
                continue
            if not rec.line_ids:
                rec.action_compute()
            rec._check_config()
            move_lines = rec._move_lines()
            if move_lines:
                move = self.env['account.move'].create({
                    'dvz_wip_run_id': rec.id,
                    'move_type': 'entry',
                    'journal_id': rec.journal_id.id,
                    'date': rec.date,
                    'ref': _('%s: revenue recognition (WIP) at %s', rec.name, rec.date),
                    'line_ids': move_lines,
                })
                move.action_post()
                reversal = move._reverse_moves(
                    [{'date': rec.date + timedelta(days=1), 'ref': _('Reversal of %s', move.ref),
                      'dvz_wip_run_id': rec.id}])
                reversal._post(soft=True)
                rec.write({'move_id': move.id, 'reversal_move_id': reversal.id})
            rec.state = 'posted'
        return True

    def _move_lines(self):
        self.ensure_one()
        c = self.company_id
        cur = self.currency_id
        lines = []

        def line(account, debit, credit, contract, label, analytic=False):
            vals = {'account_id': account.id, 'debit': debit, 'credit': credit, 'name': label,
                    'partner_id': contract.partner_id.id}
            if analytic and contract.analytic_account_id:
                vals['analytic_distribution'] = {str(contract.analytic_account_id.id): 100.0}
            return (0, 0, vals)

        for wl in self.line_ids:
            contract = wl.contract_id
            adj = cur.round(wl.adjustment)
            if adj > 0:
                label = _('%s: unbilled revenue', contract.name)
                lines += [line(c.dvz_wip_asset_account_id, adj, 0.0, contract, label),
                          line(c.dvz_wip_revenue_account_id, 0.0, adj, contract, label, analytic=True)]
            elif adj < 0:
                label = _('%s: billings in excess of work done', contract.name)
                lines += [line(c.dvz_wip_revenue_account_id, -adj, 0.0, contract, label, analytic=True),
                          line(c.dvz_wip_liability_account_id, 0.0, -adj, contract, label)]
            prov = cur.round(wl.loss_provision)
            if prov > 0:
                label = _('%s: provision for expected loss', contract.name)
                lines += [line(c.dvz_wip_loss_account_id, prov, 0.0, contract, label),
                          line(c.dvz_wip_provision_account_id, 0.0, prov, contract, label)]
        return lines

    def action_cancel(self):
        for rec in self:
            for move in (rec.reversal_move_id | rec.move_id):
                if move.state == 'posted':
                    move.button_draft()
                move.button_cancel()
            rec.write({'state': 'cancel', 'move_id': False, 'reversal_move_id': False})
        return True

    def action_draft(self):
        self.filtered(lambda r: r.state == 'cancel').write({'state': 'draft'})
        return True

    def action_view_moves(self):
        self.ensure_one()
        return {
            'type': 'ir.actions.act_window',
            'name': _('WIP Entries'),
            'res_model': 'account.move',
            'view_mode': 'list,form',
            'domain': [('id', 'in', (self.move_id | self.reversal_move_id).ids)],
        }


class AccountMove(models.Model):
    _inherit = 'account.move'

    dvz_wip_run_id = fields.Many2one('dvz.wip.run', 'WIP Run', copy=False, readonly=True, index='btree_not_null')


class DvzWipLine(models.Model):
    _name = 'dvz.wip.line'
    _description = 'WIP Line'
    _order = 'run_id desc, contract_id'

    run_id = fields.Many2one('dvz.wip.run', required=True, ondelete='cascade', index=True)
    run_state = fields.Selection(related='run_id.state')
    date = fields.Date(related='run_id.date', store=True)
    company_id = fields.Many2one(related='run_id.company_id', store=True)
    currency_id = fields.Many2one(related='run_id.currency_id')
    contract_id = fields.Many2one('dvz.contract', 'Contract', required=True, index=True)
    partner_id = fields.Many2one(related='contract_id.partner_id', store=True, string='Client')
    method = fields.Selection(WIP_METHODS, 'Method', required=True)
    contract_value = fields.Monetary('Contract Value')
    cost_to_date = fields.Monetary('Cost to Date')
    forecast_cost = fields.Monetary('Forecast Final Cost')
    certified = fields.Monetary('Certified to Date')
    billed = fields.Monetary('Invoiced to Date', help='Work done invoiced on posted certificate invoices.')
    percent = fields.Float('Progress %', digits=(16, 2))
    earned = fields.Monetary('Revenue Earned', compute='_compute_wip', store=True)
    adjustment = fields.Monetary('Over / Under Billing', compute='_compute_wip', store=True,
                                 help='Positive: under-billed, earned more than invoiced (contract asset).\n'
                                      'Negative: over-billed, invoiced more than earned (contract liability).')
    position = fields.Selection([('under', 'Under-billed'), ('over', 'Over-billed'), ('even', 'In line')],
                                compute='_compute_wip', store=True)
    forecast_margin = fields.Monetary('Forecast Margin', compute='_compute_wip', store=True)
    loss_provision = fields.Monetary('Loss Provision', compute='_compute_wip', store=True,
                                     help='Expected loss not yet in profit and loss, provided for in full now.')

    @api.depends('percent', 'contract_value', 'billed', 'forecast_cost', 'cost_to_date')
    def _compute_wip(self):
        for line in self:
            earned = line.contract_value * line.percent / 100.0
            line.earned = earned
            line.adjustment = earned - line.billed
            rounding = line.currency_id.rounding if line.currency_id else 0.01
            line.position = 'under' if line.adjustment > rounding else 'over' if line.adjustment < -rounding else 'even'
            line.forecast_margin = line.contract_value - line.forecast_cost
            expected_loss = max(line.forecast_cost - line.contract_value, 0.0)
            loss_in_pl = max(line.cost_to_date - earned, 0.0)
            line.loss_provision = max(expected_loss - loss_in_pl, 0.0)
