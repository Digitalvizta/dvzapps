from datetime import timedelta

from dateutil.relativedelta import relativedelta
from markupsafe import Markup

from odoo import _, api, fields, models
from odoo.exceptions import UserError, ValidationError

FRIDAY = 4  # date.weekday(): Monday=0 ... Friday=4


class ManpowerTimesheet(models.Model):
    _name = 'dvz.manpower.timesheet'
    _description = 'Manpower Timesheet'
    _inherit = ['portal.mixin', 'mail.thread', 'mail.activity.mixin']
    _order = 'date_from desc, id desc'

    def _default_date_from(self):
        return fields.Date.context_today(self).replace(day=1)

    def _default_date_to(self):
        return fields.Date.context_today(self).replace(day=1) + relativedelta(months=1, days=-1)

    name = fields.Char(string='Reference', required=True, copy=False, readonly=True, default=lambda self: _('New'))
    contract_id = fields.Many2one(
        'dvz.manpower.contract', string='Supply Contract', required=True, index=True, tracking=True,
        domain="[('state', 'in', ('active', 'expired'))]")
    partner_id = fields.Many2one(related='contract_id.partner_id', store=True, string='Client')
    company_id = fields.Many2one(related='contract_id.company_id', store=True)
    date_from = fields.Date(string='From', required=True, default=_default_date_from, tracking=True)
    date_to = fields.Date(string='To', required=True, default=_default_date_to, tracking=True)
    state = fields.Selection([
        ('draft', 'Draft'),
        ('submitted', 'Waiting Client Approval'),
        ('approved', 'Approved'),
        ('rejected', 'Rejected'),
    ], default='draft', required=True, tracking=True, copy=False)
    line_ids = fields.One2many('dvz.manpower.timesheet.line', 'sheet_id', string='Workers', copy=True)
    total_days = fields.Float(compute='_compute_totals', store=True)
    total_hours = fields.Float(compute='_compute_totals', store=True)
    total_overtime = fields.Float(string='Total Overtime', compute='_compute_totals', store=True)
    approved_by = fields.Char(string='Approved / Rejected By', readonly=True, copy=False, tracking=True)
    approval_date = fields.Datetime(readonly=True, copy=False)
    reject_reason = fields.Text(readonly=True, copy=False)

    @api.depends('line_ids.days_worked', 'line_ids.regular_hours', 'line_ids.overtime_hours')
    def _compute_totals(self):
        for sheet in self:
            sheet.total_days = sum(sheet.line_ids.mapped('days_worked'))
            sheet.total_hours = sum(sheet.line_ids.mapped('regular_hours'))
            sheet.total_overtime = sum(sheet.line_ids.mapped('overtime_hours'))

    def _compute_access_url(self):
        super()._compute_access_url()
        for sheet in self:
            sheet.access_url = '/my/manpower/timesheets/%s' % sheet.id

    @api.constrains('date_from', 'date_to')
    def _check_dates(self):
        for sheet in self:
            if sheet.date_to < sheet.date_from:
                raise ValidationError(_('The period end cannot be before its start.'))

    @api.model_create_multi
    def create(self, vals_list):
        for vals in vals_list:
            if vals.get('name', _('New')) == _('New'):
                vals['name'] = self.env['ir.sequence'].next_by_code('dvz.manpower.timesheet') or _('New')
        return super().create(vals_list)

    @staticmethod
    def _count_working_days(start, end):
        days = 0
        current = start
        while current <= end:
            if current.weekday() != FRIDAY:
                days += 1
            current += timedelta(days=1)
        return days

    def action_generate_lines(self):
        for sheet in self:
            if sheet.state != 'draft':
                raise UserError(_('You can only fill lines on a draft timesheet.'))
            daily_hours = sheet.company_id.dv_daily_hours or 8.0
            assignments = sheet.contract_id.assignment_ids.filtered(
                lambda a: a.state in ('active', 'ended')
                and a.date_start <= sheet.date_to
                and (not a.date_end or a.date_end >= sheet.date_from))
            existing = sheet.line_ids.mapped('assignment_id')
            commands = []
            for assignment in assignments - existing:
                start = max(assignment.date_start, sheet.date_from)
                end = min(assignment.date_end or sheet.date_to, sheet.date_to)
                days = self._count_working_days(start, end)
                commands.append((0, 0, {
                    'assignment_id': assignment.id,
                    'employee_id': assignment.employee_id.id,
                    'job_id': assignment.job_id.id,
                    'days_worked': days,
                    'regular_hours': days * daily_hours,
                }))
            if commands:
                sheet.write({'line_ids': commands})

    def action_submit(self):
        for sheet in self:
            if not sheet.line_ids:
                raise UserError(_('Add worker lines before sending %s to the client.', sheet.name))
            sheet._portal_ensure_token()
            sheet.state = 'submitted'
            sheet.message_subscribe(partner_ids=sheet.partner_id.ids)
            link = sheet.get_base_url() + sheet.get_portal_url()
            sheet.message_post(
                body=Markup(_(
                    'Timesheet %(name)s for %(start)s to %(end)s is ready for your approval: '
                    '<a href="%(link)s">review and approve online</a>.'
                )) % {'name': sheet.name, 'start': sheet.date_from, 'end': sheet.date_to, 'link': link},
                partner_ids=sheet.partner_id.ids,
                message_type='comment',
                subtype_xmlid='mail.mt_comment',
            )

    def _portal_set_decision(self, approved, by_name, reason=False):
        """Called from the portal (sudo) or from the back-end."""
        for sheet in self:
            if sheet.state != 'submitted':
                raise UserError(_('Only timesheets waiting for approval can be approved or rejected.'))
            sheet.write({
                'state': 'approved' if approved else 'rejected',
                'approved_by': by_name,
                'approval_date': fields.Datetime.now(),
                'reject_reason': False if approved else reason,
            })
            if approved:
                sheet.message_post(body=_('Timesheet approved by %s.', by_name))
            else:
                sheet.message_post(body=_('Timesheet rejected by %(who)s. Reason: %(reason)s',
                                          who=by_name, reason=reason or '-'))
                sheet.activity_schedule(
                    'mail.mail_activity_data_todo',
                    summary=_('Client rejected timesheet %s', sheet.name),
                    user_id=sheet.contract_id.user_id.id or self.env.user.id,
                )

    def action_approve_internal(self):
        self._portal_set_decision(True, self.env.user.name)

    def action_draft(self):
        self.write({'state': 'draft', 'approved_by': False, 'approval_date': False})

    def action_preview_portal(self):
        self.ensure_one()
        self._portal_ensure_token()
        return {
            'type': 'ir.actions.act_url',
            'target': 'new',
            'url': self.get_portal_url(),
        }


class ManpowerTimesheetLine(models.Model):
    _name = 'dvz.manpower.timesheet.line'
    _description = 'Manpower Timesheet Line'
    _order = 'employee_id'

    sheet_id = fields.Many2one('dvz.manpower.timesheet', required=True, ondelete='cascade', index=True)
    contract_id = fields.Many2one(related='sheet_id.contract_id', store=True)
    company_id = fields.Many2one(related='sheet_id.company_id', store=True)
    assignment_id = fields.Many2one('dvz.manpower.assignment', string='Assignment')
    employee_id = fields.Many2one('hr.employee', string='Worker', required=True)
    job_id = fields.Many2one('hr.job', string='Job Position')
    days_worked = fields.Float(string='Days Worked')
    regular_hours = fields.Float(string='Regular Hours')
    overtime_hours = fields.Float(string='Overtime Hours')
    note = fields.Char()
