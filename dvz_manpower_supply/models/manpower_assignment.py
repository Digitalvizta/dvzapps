from odoo import _, api, fields, models
from odoo.exceptions import ValidationError


class ManpowerAssignment(models.Model):
    _name = 'dvz.manpower.assignment'
    _description = 'Worker Assignment'
    _inherit = ['mail.thread']
    _order = 'date_start desc, id desc'
    _rec_name = 'employee_id'

    contract_id = fields.Many2one(
        'dvz.manpower.contract', string='Contract', required=True, index=True,
        ondelete='cascade', tracking=True)
    partner_id = fields.Many2one(related='contract_id.partner_id', store=True, string='Client')
    company_id = fields.Many2one(related='contract_id.company_id', store=True)
    employee_id = fields.Many2one('hr.employee', string='Worker', required=True, index=True, tracking=True)
    job_id = fields.Many2one(
        'hr.job', string='Job Position', tracking=True,
        compute='_compute_job_id', store=True, readonly=False)
    site = fields.Char(
        string='Site', compute='_compute_site', store=True, readonly=False)
    date_start = fields.Date(string='From', required=True, default=fields.Date.context_today, tracking=True)
    date_end = fields.Date(string='To', tracking=True)
    state = fields.Selection([
        ('planned', 'Planned'),
        ('active', 'Active'),
        ('ended', 'Ended'),
    ], default='planned', required=True, tracking=True)

    @api.depends('employee_id')
    def _compute_job_id(self):
        for rec in self:
            rec.job_id = rec.job_id or rec.employee_id.job_id

    @api.depends('contract_id')
    def _compute_site(self):
        for rec in self:
            rec.site = rec.site or rec.contract_id.site

    @api.constrains('employee_id', 'state', 'date_start', 'date_end')
    def _check_double_assignment(self):
        for rec in self.filtered(lambda r: r.state == 'active'):
            overlap = self.search([
                ('id', '!=', rec.id),
                ('employee_id', '=', rec.employee_id.id),
                ('state', '=', 'active'),
            ], limit=1)
            if overlap:
                raise ValidationError(_(
                    '%(worker)s is already active at %(client)s (%(contract)s). '
                    'End that assignment first.',
                    worker=rec.employee_id.name,
                    client=overlap.partner_id.display_name,
                    contract=overlap.contract_id.name,
                ))

    @api.constrains('date_start', 'date_end')
    def _check_dates(self):
        for rec in self:
            if rec.date_end and rec.date_end < rec.date_start:
                raise ValidationError(_('The assignment end date cannot be before its start date.'))

    def action_start(self):
        self.write({'state': 'active'})

    def action_end(self):
        today = fields.Date.context_today(self)
        for rec in self:
            rec.write({'state': 'ended', 'date_end': rec.date_end or today})
