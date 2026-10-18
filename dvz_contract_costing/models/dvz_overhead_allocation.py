from odoo import _, api, fields, models
from odoo.exceptions import UserError

from .cost_types import DIRECT_TYPES


class DvzOverheadAllocation(models.Model):
    _name = 'dvz.overhead.allocation'
    _description = 'Head-Office Overhead Allocation'
    _inherit = ['mail.thread']
    _order = 'date desc, id desc'
    _check_company_auto = True

    name = fields.Char('Reference', required=True, copy=False, readonly=True, default=lambda self: _('New'))
    description = fields.Char('Description', required=True,
                              default=lambda self: _('Head-office overheads'),
                              help='e.g. "Head-office salaries and rent, March"')
    company_id = fields.Many2one('res.company', required=True, default=lambda self: self.env.company)
    currency_id = fields.Many2one(related='company_id.currency_id')
    date = fields.Date('Allocation Date', required=True, default=fields.Date.context_today)
    date_from = fields.Date('Period From', required=True,
                            default=lambda self: fields.Date.context_today(self).replace(day=1))
    date_to = fields.Date('Period To', required=True, default=fields.Date.context_today)
    amount = fields.Monetary('Amount to Allocate', required=True, tracking=True,
                             help='Head-office cost of the period to share across contracts.')
    basis = fields.Selection([
        ('direct_cost', 'Direct cost in the period'),
        ('labour_hours', 'Labour hours in the period'),
        ('value', 'Contract value'),
        ('equal', 'Equal share'),
    ], required=True, default='direct_cost', tracking=True,
        help='How the amount is shared: in proportion to each contract\'s direct cost or labour hours '
             'posted in the period, to the contract value, or equally.')
    contract_ids = fields.Many2many(
        'dvz.contract', string='Contracts', check_company=True,
        domain="[('contract_type', '=', 'client'), ('state', 'in', ('progress', 'handover')), "
               "('analytic_account_id', '!=', False)]",
        default=lambda self: self.env['dvz.contract'].search([
            ('contract_type', '=', 'client'), ('state', '=', 'progress'),
            ('analytic_account_id', '!=', False), ('company_id', '=', self.env.company.id)]))
    line_ids = fields.One2many('dvz.overhead.allocation.line', 'allocation_id', 'Shares', copy=False)
    analytic_line_ids = fields.One2many('account.analytic.line', 'dvz_allocation_id', 'Cost Lines', readonly=True)
    state = fields.Selection([('draft', 'Draft'), ('posted', 'Posted'), ('cancel', 'Cancelled')],
                             default='draft', required=True, tracking=True, copy=False)

    @api.model_create_multi
    def create(self, vals_list):
        for vals in vals_list:
            if vals.get('name', _('New')) == _('New'):
                vals['name'] = self.env['ir.sequence'].next_by_code('dvz.overhead.allocation') or _('New')
        return super().create(vals_list)

    def _basis_weights(self):
        self.ensure_one()
        contracts = self.contract_ids
        weights = {}
        if self.basis == 'equal':
            return {c.id: 1.0 for c in contracts}
        if self.basis == 'value':
            return {c.id: c.amount_untaxed for c in contracts}
        domain = [('dvz_contract_id', 'in', contracts.ids), ('dvz_cost_type', '!=', False),
                  ('date', '>=', self.date_from), ('date', '<=', self.date_to),
                  ('dvz_allocation_id', '=', False)]
        if self.basis == 'labour_hours':
            domain.append(('dvz_cost_type', '=', 'labour'))
            agg = 'unit_amount:sum'
        else:
            domain.append(('dvz_cost_type', 'in', list(DIRECT_TYPES)))
            agg = 'amount:sum'
        for contract, value in self.env['account.analytic.line'].sudo()._read_group(
                domain, ['dvz_contract_id'], [agg]):
            weights[contract.id] = abs(value)
        return weights

    def action_compute(self):
        for rec in self:
            if rec.state != 'draft':
                raise UserError(_('Only draft allocations can be recalculated.'))
            if not rec.contract_ids:
                raise UserError(_('Choose at least one contract.'))
            if rec.date_to < rec.date_from:
                raise UserError(_('The period end is before its start.'))
            weights = rec._basis_weights()
            total = sum(weights.values())
            if not total:
                raise UserError(_('None of the chosen contracts has any %s in this period. '
                                  'Choose another basis or period.',
                                  dict(self._fields['basis']._description_selection(self.env))[rec.basis].lower()))
            cur = rec.currency_id
            lines, allocated = [], 0.0
            items = [(cid, w) for cid, w in weights.items() if w]
            for i, (cid, w) in enumerate(items):
                share = w / total
                amount = cur.round(rec.amount * share) if i < len(items) - 1 else cur.round(rec.amount - allocated)
                allocated += amount
                lines.append((0, 0, {'contract_id': cid, 'share_percent': share * 100.0, 'amount': amount,
                                     'basis_value': w}))
            rec.line_ids = [(5, 0, 0)] + lines
        return True

    def action_post(self):
        AnalyticLine = self.env['account.analytic.line'].sudo()
        for rec in self:
            if rec.state != 'draft':
                continue
            if not rec.line_ids:
                rec.action_compute()
            if rec.currency_id.compare_amounts(sum(rec.line_ids.mapped('amount')), rec.amount):
                raise UserError(_('The shares do not add up to the amount to allocate. Press "Calculate shares" again.'))
            vals_list = []
            for line in rec.line_ids:
                contract = line.contract_id
                column = contract._analytic_column()
                if not column or not line.amount:
                    continue
                vals_list.append({
                    'name': '%s: %s' % (rec.name, rec.description),
                    'date': rec.date,
                    'amount': -line.amount,
                    'company_id': rec.company_id.id,
                    column: contract.analytic_account_id.id,
                    'dvz_allocation_id': rec.id,
                    'dvz_cost_type': 'ho_overhead',
                    'ref': rec.name,
                })
            AnalyticLine.with_context(dvz_no_manual=True).create(vals_list)
            rec.state = 'posted'
        return True

    def action_cancel(self):
        for rec in self:
            rec.analytic_line_ids.sudo().unlink()
            rec.state = 'cancel'
        return True

    def action_draft(self):
        self.filtered(lambda r: r.state == 'cancel').write({'state': 'draft'})
        return True

    def unlink(self):
        if any(rec.state == 'posted' for rec in self):
            raise UserError(_('Cancel a posted allocation before deleting it.'))
        return super().unlink()


class DvzOverheadAllocationLine(models.Model):
    _name = 'dvz.overhead.allocation.line'
    _description = 'Overhead Allocation Share'
    _order = 'amount desc'

    allocation_id = fields.Many2one('dvz.overhead.allocation', required=True, ondelete='cascade', index=True)
    currency_id = fields.Many2one(related='allocation_id.currency_id')
    contract_id = fields.Many2one('dvz.contract', 'Contract', required=True)
    basis_value = fields.Float('Basis', digits=(16, 2))
    share_percent = fields.Float('Share %', digits=(16, 2))
    amount = fields.Monetary('Allocated')
