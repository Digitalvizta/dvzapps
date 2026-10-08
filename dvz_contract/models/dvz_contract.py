from dateutil.relativedelta import relativedelta

from odoo import _, api, fields, models
from odoo.exceptions import UserError, ValidationError


class DvzContract(models.Model):
    _name = 'dvz.contract'
    _description = 'Construction Contract'
    _inherit = ['mail.thread', 'mail.activity.mixin']
    _order = 'date_start desc, id desc'
    _check_company_auto = True

    name = fields.Char('Reference', required=True, copy=False, readonly=True, default=lambda self: _('New'), tracking=True)
    title = fields.Char('Contract Title', tracking=True)
    contract_type = fields.Selection([('client', 'Client Contract')], string='Type', default='client', required=True, index=True)
    state = fields.Selection([
        ('draft', 'Draft'),
        ('progress', 'In Progress'),
        ('handover', 'Handed Over'),
        ('closed', 'Closed'),
        ('cancel', 'Cancelled'),
    ], default='draft', required=True, tracking=True, copy=False, index=True)
    partner_id = fields.Many2one('res.partner', 'Client', required=True, tracking=True, check_company=True)
    project_id = fields.Many2one('project.project', 'Project', tracking=True, check_company=True)
    user_id = fields.Many2one('res.users', 'Contract Manager', default=lambda self: self.env.user, tracking=True)
    company_id = fields.Many2one('res.company', required=True, default=lambda self: self.env.company, index=True)
    currency_id = fields.Many2one(
        'res.currency', required=True, tracking=True,
        default=lambda self: self.env.company.currency_id)
    date_signed = fields.Date('Signed On')
    date_start = fields.Date('Start Date', default=fields.Date.context_today, tracking=True)
    date_end = fields.Date('Planned Completion', tracking=True)
    handover_date = fields.Date('Handover Date', copy=False, tracking=True)
    defects_months = fields.Integer(
        'Defects Liability (months)', default=lambda self: self.env.company.dvz_defects_months)
    dlp_end_date = fields.Date('Defects Period Ends', compute='_compute_dlp_end_date', store=True)

    retention_percent = fields.Float(
        'Retention %', default=lambda self: self.env.company.dvz_retention_percent, tracking=True)
    advance_percent = fields.Float(
        'Advance Payment %', default=lambda self: self.env.company.dvz_advance_percent, tracking=True)
    advance_recovery_percent = fields.Float(
        'Advance Recovery %', default=lambda self: self.env.company.dvz_advance_recovery_percent,
        help='Percentage of each certificate deducted to recover the advance payment.')
    tax_ids = fields.Many2many(
        'account.tax', 'dvz_contract_tax_rel', 'contract_id', 'tax_id', string='Taxes',
        default=lambda self: self.env.company.dvz_sale_tax_ids, check_company=True)

    line_ids = fields.One2many('dvz.contract.line', 'contract_id', 'Bill of Quantities', copy=True)
    amount_untaxed = fields.Monetary('Contract Value', compute='_compute_amounts', store=True, tracking=True)
    cost_budget = fields.Monetary('Cost Budget', compute='_compute_amounts', store=True)
    planned_margin = fields.Monetary('Planned Margin', compute='_compute_amounts', store=True)
    planned_margin_percent = fields.Float('Planned Margin %', compute='_compute_amounts', store=True)
    boq_locked = fields.Boolean('BOQ Locked', compute='_compute_boq_locked')

    analytic_account_id = fields.Many2one(
        'account.analytic.account', 'Analytic Account', copy=False, check_company=True, tracking=True)
    committed_cost = fields.Monetary('Committed Cost', compute='_compute_cost_control',
                                     help='Open purchase order amounts not yet billed.')
    actual_cost = fields.Monetary('Actual Cost', compute='_compute_cost_control')
    actual_revenue = fields.Monetary('Actual Revenue', compute='_compute_cost_control')
    forecast_cost = fields.Monetary('Forecast Cost', compute='_compute_cost_control',
                                    help='Actual cost plus committed cost.')
    budget_remaining = fields.Monetary('Budget Remaining', compute='_compute_cost_control')

    scope = fields.Html('Scope of Work')
    notes = fields.Html('Terms & Notes')
    color = fields.Integer()

    _name_uniq = models.Constraint('unique(name, company_id)', 'The contract reference must be unique per company.')

    # ------------------------------------------------------------------
    # Computes
    # ------------------------------------------------------------------
    @api.depends('handover_date', 'defects_months')
    def _compute_dlp_end_date(self):
        for rec in self:
            rec.dlp_end_date = rec.handover_date and rec.handover_date + relativedelta(months=rec.defects_months or 0)

    @api.depends('line_ids.price_subtotal', 'line_ids.cost_subtotal', 'line_ids.display_type')
    def _compute_amounts(self):
        for rec in self:
            lines = rec.line_ids.filtered(lambda l: not l.display_type)
            value = sum(lines.mapped('price_subtotal'))
            cost = sum(lines.mapped('cost_subtotal'))
            rec.amount_untaxed = value
            rec.cost_budget = cost
            rec.planned_margin = value - cost if cost else 0.0
            rec.planned_margin_percent = (value - cost) / value * 100.0 if (value and cost) else 0.0

    @api.depends('state', 'company_id.dvz_lock_boq')
    def _compute_boq_locked(self):
        for rec in self:
            rec.boq_locked = rec.state != 'draft' and rec.company_id.dvz_lock_boq

    def _analytic_column(self):
        self.ensure_one()
        if not self.analytic_account_id:
            return False
        return self.analytic_account_id.plan_id._column_name()

    def _compute_cost_control(self):
        AnalyticLine = self.env['account.analytic.line'].sudo()
        has_purchase = 'purchase.order.line' in self.env
        for rec in self:
            cost = revenue = committed = 0.0
            col = rec._analytic_column()
            if col and col in AnalyticLine._fields:
                lines = AnalyticLine.search([(col, '=', rec.analytic_account_id.id)])
                for line in lines:
                    amount = line.currency_id._convert(
                        line.amount, rec.currency_id, rec.company_id, line.date or fields.Date.today()) \
                        if line.currency_id and line.currency_id != rec.currency_id else line.amount
                    if amount < 0:
                        cost += -amount
                    else:
                        revenue += amount
            if has_purchase and rec.analytic_account_id:
                committed = rec._compute_committed_cost()
            rec.actual_cost = cost
            rec.actual_revenue = revenue
            rec.committed_cost = committed
            rec.forecast_cost = cost + committed
            rec.budget_remaining = rec.cost_budget - cost - committed if rec.cost_budget else 0.0

    def _compute_committed_cost(self):
        """Untaxed amount of confirmed purchase lines not yet billed, on this contract's analytic account."""
        self.ensure_one()
        key = str(self.analytic_account_id.id)
        pol = self.env['purchase.order.line'].sudo().search([
            ('order_id.state', '=', 'purchase'),
            ('company_id', '=', self.company_id.id),
            ('analytic_distribution', '!=', False),
        ])
        total = 0.0
        for line in pol:
            dist = line.analytic_distribution or {}
            share = 0.0
            for k, v in dist.items():
                if key in str(k).split(','):
                    share += v
            if not share:
                continue
            open_qty = max(line.product_qty - line.qty_invoiced, 0.0)
            amount = open_qty * line.price_unit * share / 100.0
            if line.currency_id != self.currency_id:
                amount = line.currency_id._convert(amount, self.currency_id, self.company_id, fields.Date.today())
            total += amount
        return total

    # ------------------------------------------------------------------
    # ORM
    # ------------------------------------------------------------------
    @api.model_create_multi
    def create(self, vals_list):
        for vals in vals_list:
            if vals.get('name', _('New')) == _('New'):
                vals['name'] = self._get_sequence_name(vals)
        return super().create(vals_list)

    @api.model
    def _get_sequence_name(self, vals):
        company = self.env['res.company'].browse(vals.get('company_id')) if vals.get('company_id') else self.env.company
        ctype = vals.get('contract_type') or self.env.context.get('default_contract_type') or 'client'
        code = 'dvz.contract.%s' % ctype
        seq = self.env['ir.sequence'].with_company(company).next_by_code(code)
        return seq or self.env['ir.sequence'].with_company(company).next_by_code('dvz.contract.client') or _('New')

    @api.onchange('project_id')
    def _onchange_project_id(self):
        if self.project_id and self.project_id.partner_id and not self.partner_id:
            self.partner_id = self.project_id.partner_id

    @api.constrains('retention_percent', 'advance_percent', 'advance_recovery_percent')
    def _check_percents(self):
        for rec in self:
            for fname in ('retention_percent', 'advance_percent', 'advance_recovery_percent'):
                if not 0.0 <= rec[fname] <= 100.0:
                    raise ValidationError(_('Percentages must be between 0 and 100.'))

    @api.constrains('date_start', 'date_end')
    def _check_dates(self):
        for rec in self:
            if rec.date_start and rec.date_end and rec.date_end < rec.date_start:
                raise ValidationError(_('The planned completion date cannot be before the start date.'))

    def unlink(self):
        if any(rec.state not in ('draft', 'cancel') for rec in self):
            raise UserError(_('You can only delete draft or cancelled contracts.'))
        return super().unlink()

    # ------------------------------------------------------------------
    # Actions
    # ------------------------------------------------------------------
    def action_confirm(self):
        for rec in self:
            if rec.state != 'draft':
                continue
            if not rec.line_ids.filtered(lambda l: not l.display_type):
                raise UserError(_('Add at least one BOQ item before confirming %s.', rec.name))
            if rec.company_id.dvz_analytic_per_contract and not rec.analytic_account_id:
                rec.analytic_account_id = rec._get_or_create_analytic_account()
            rec.state = 'progress'
            if not rec.date_signed:
                rec.date_signed = fields.Date.context_today(rec)
        return True

    def _get_or_create_analytic_account(self):
        self.ensure_one()
        if self.project_id and self.project_id.account_id:
            return self.project_id.account_id
        plan = self.company_id.dvz_analytic_plan_id
        if not plan:
            plan, _others = self.env['account.analytic.plan']._get_all_plans()
        account = self.env['account.analytic.account'].create({
            'name': '%s - %s' % (self.name, self.title or self.partner_id.name),
            'code': self.name,
            'plan_id': plan.id,
            'partner_id': self.partner_id.id,
            'company_id': self.company_id.id,
        })
        if self.project_id and not self.project_id.account_id:
            self.project_id.account_id = account
        return account

    def action_handover(self):
        for rec in self:
            if rec.state != 'progress':
                raise UserError(_('Only contracts in progress can be handed over.'))
            rec.write({'state': 'handover', 'handover_date': rec.handover_date or fields.Date.context_today(rec)})
        return True

    def action_close(self):
        self.write({'state': 'closed'})
        return True

    def action_cancel(self):
        self.write({'state': 'cancel'})
        return True

    def action_draft(self):
        for rec in self:
            if rec.state != 'cancel':
                raise UserError(_('Only cancelled contracts can be reset to draft.'))
        self.write({'state': 'draft'})
        return True

    def action_view_analytic_lines(self):
        self.ensure_one()
        col = self._analytic_column() or 'account_id'
        return {
            'type': 'ir.actions.act_window',
            'name': _('Costs & Revenues'),
            'res_model': 'account.analytic.line',
            'view_mode': 'list,pivot,graph,form',
            'domain': [(col, '=', self.analytic_account_id.id)],
            'context': {'search_default_group_date': 1},
        }
