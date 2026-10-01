from odoo import _, api, fields, models
from odoo.exceptions import UserError, ValidationError


class ManpowerContract(models.Model):
    _name = 'dv.manpower.contract'
    _description = 'Manpower Supply Contract'
    _inherit = ['mail.thread', 'mail.activity.mixin']
    _order = 'date_start desc, id desc'

    name = fields.Char(
        string='Contract Reference', required=True, copy=False, readonly=True,
        default=lambda self: _('New'), tracking=True)
    client_reference = fields.Char(string='Client PO / Reference', tracking=True)
    partner_id = fields.Many2one(
        'res.partner', string='Client', required=True, tracking=True, index=True)
    user_id = fields.Many2one(
        'res.users', string='Account Manager', default=lambda self: self.env.user, tracking=True)
    company_id = fields.Many2one(
        'res.company', required=True, default=lambda self: self.env.company, index=True)
    currency_id = fields.Many2one(related='company_id.currency_id', store=True)
    date_start = fields.Date(string='Start Date', required=True, default=fields.Date.context_today, tracking=True)
    date_end = fields.Date(string='End Date', tracking=True)
    site = fields.Char(string='Work Site / Location', tracking=True)
    state = fields.Selection([
        ('draft', 'Draft'),
        ('active', 'Active'),
        ('expired', 'Expired'),
        ('cancelled', 'Cancelled'),
    ], default='draft', required=True, tracking=True, copy=False)
    line_ids = fields.One2many('dv.manpower.contract.line', 'contract_id', string='Rates', copy=True)
    assignment_ids = fields.One2many('dv.manpower.assignment', 'contract_id', string='Assignments')
    required_workers = fields.Integer(compute='_compute_worker_counts', store=True)
    assigned_workers = fields.Integer(compute='_compute_worker_counts', store=True)
    notes = fields.Html(string='Terms & Notes')

    @api.depends('line_ids.quantity', 'assignment_ids.state')
    def _compute_worker_counts(self):
        for contract in self:
            contract.required_workers = sum(contract.line_ids.mapped('quantity'))
            contract.assigned_workers = len(
                contract.assignment_ids.filtered(lambda a: a.state == 'active'))

    @api.constrains('date_start', 'date_end')
    def _check_dates(self):
        for contract in self:
            if contract.date_end and contract.date_end < contract.date_start:
                raise ValidationError(_('The end date cannot be before the start date.'))

    @api.model_create_multi
    def create(self, vals_list):
        for vals in vals_list:
            if vals.get('name', _('New')) == _('New'):
                vals['name'] = self.env['ir.sequence'].next_by_code('dv.manpower.contract') or _('New')
        return super().create(vals_list)

    def action_activate(self):
        for contract in self:
            if not contract.line_ids:
                raise UserError(_('Add at least one rate line before activating %s.', contract.name))
        self.write({'state': 'active'})

    def action_cancel(self):
        self.assignment_ids.filtered(lambda a: a.state in ('planned', 'active')).write({'state': 'ended'})
        self.write({'state': 'cancelled'})

    def action_draft(self):
        self.write({'state': 'draft'})

    def action_view_assignments(self):
        self.ensure_one()
        return {
            'type': 'ir.actions.act_window',
            'name': _('Assignments'),
            'res_model': 'dv.manpower.assignment',
            'view_mode': 'list,form',
            'domain': [('contract_id', '=', self.id)],
            'context': {'default_contract_id': self.id},
        }

    @api.model
    def _cron_expire_contracts(self):
        today = fields.Date.context_today(self)
        expired = self.search([('state', '=', 'active'), ('date_end', '!=', False), ('date_end', '<', today)])
        expired.write({'state': 'expired'})
        expired.assignment_ids.filtered(lambda a: a.state == 'active').write({'state': 'ended'})
        for contract in expired:
            contract.message_post(body=_('Contract expired automatically on its end date.'))


class ManpowerContractLine(models.Model):
    _name = 'dv.manpower.contract.line'
    _description = 'Manpower Contract Rate Line'
    _order = 'sequence, id'

    sequence = fields.Integer(default=10)
    contract_id = fields.Many2one('dv.manpower.contract', required=True, ondelete='cascade', index=True)
    job_id = fields.Many2one('hr.job', string='Job Position', required=True)
    quantity = fields.Integer(string='Workers Required', default=1)
    rate_type = fields.Selection([
        ('hour', 'Per Hour'),
        ('day', 'Per Day'),
        ('month', 'Per Month'),
    ], default='month', required=True)
    rate = fields.Monetary(string='Rate', currency_field='currency_id')
    currency_id = fields.Many2one(related='contract_id.currency_id')
    company_id = fields.Many2one(related='contract_id.company_id', store=True)
