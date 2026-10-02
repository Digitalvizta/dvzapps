from datetime import timedelta

from dateutil.relativedelta import relativedelta
from markupsafe import Markup

from odoo import _, api, fields, models
from odoo.exceptions import UserError, ValidationError

FRIDAY = 4  # date.weekday(): Monday=0 ... Friday=4


class EquipmentLogsheet(models.Model):
    _name = 'dvz.equipment.logsheet'
    _description = 'Equipment Log Sheet'
    _inherit = ['portal.mixin', 'mail.thread', 'mail.activity.mixin']
    _order = 'date_from desc, id desc'

    def _default_date_from(self):
        return fields.Date.context_today(self).replace(day=1)

    def _default_date_to(self):
        return fields.Date.context_today(self).replace(day=1) + relativedelta(months=1, days=-1)

    name = fields.Char(string='Reference', required=True, copy=False, readonly=True, default=lambda self: _('New'))
    contract_id = fields.Many2one(
        'dvz.rental.contract', string='Rental Contract', required=True, index=True, tracking=True,
        domain="[('state', 'in', ('on_rent', 'returned'))]")
    partner_id = fields.Many2one(related='contract_id.partner_id', store=True, string='Client')
    company_id = fields.Many2one(related='contract_id.company_id', store=True)
    site = fields.Char(related='contract_id.site')
    date_from = fields.Date(string='From', required=True, default=_default_date_from, tracking=True)
    date_to = fields.Date(string='To', required=True, default=_default_date_to, tracking=True)
    state = fields.Selection([
        ('draft', 'Draft'),
        ('submitted', 'Waiting Client Approval'),
        ('approved', 'Approved'),
        ('rejected', 'Rejected'),
    ], default='draft', required=True, tracking=True, copy=False)
    line_ids = fields.One2many('dvz.equipment.logsheet.line', 'sheet_id', string='Daily Log', copy=True)
    total_working = fields.Float(string='Working Hours', compute='_compute_totals', store=True)
    total_idle = fields.Float(string='Idle Hours', compute='_compute_totals', store=True)
    total_breakdown = fields.Float(string='Breakdown Hours', compute='_compute_totals', store=True)
    total_fuel = fields.Float(string='Fuel (L)', compute='_compute_totals', store=True)
    approved_by = fields.Char(string='Approved / Rejected By', readonly=True, copy=False, tracking=True)
    approval_date = fields.Datetime(readonly=True, copy=False)
    reject_reason = fields.Text(readonly=True, copy=False)

    @api.depends('line_ids.working_hours', 'line_ids.idle_hours', 'line_ids.breakdown_hours', 'line_ids.fuel_liters')
    def _compute_totals(self):
        for sheet in self:
            sheet.total_working = sum(sheet.line_ids.mapped('working_hours'))
            sheet.total_idle = sum(sheet.line_ids.mapped('idle_hours'))
            sheet.total_breakdown = sum(sheet.line_ids.mapped('breakdown_hours'))
            sheet.total_fuel = sum(sheet.line_ids.mapped('fuel_liters'))

    def _compute_access_url(self):
        super()._compute_access_url()
        for sheet in self:
            sheet.access_url = '/my/equipment/logsheets/%s' % sheet.id

    @api.constrains('date_from', 'date_to')
    def _check_dates(self):
        for sheet in self:
            if sheet.date_to < sheet.date_from:
                raise ValidationError(_('The period end cannot be before its start.'))

    @api.model_create_multi
    def create(self, vals_list):
        for vals in vals_list:
            if vals.get('name', _('New')) == _('New'):
                vals['name'] = self.env['ir.sequence'].next_by_code('dvz.equipment.logsheet') or _('New')
        return super().create(vals_list)

    def action_generate_lines(self):
        """Create one line per rented machine and working day (Friday excluded)."""
        for sheet in self:
            if sheet.state != 'draft':
                raise UserError(_('You can only fill lines on a draft log sheet.'))
            daily_hours = sheet.company_id.dv_eq_daily_hours or 10.0
            existing = {(l.contract_line_id.id, l.date) for l in sheet.line_ids}
            commands = []
            for rental_line in sheet.contract_id.line_ids:
                if not rental_line.date_from:
                    continue
                start = max(rental_line.date_from, sheet.date_from)
                end = min(rental_line.date_to or sheet.date_to, sheet.date_to)
                current = start
                while current <= end:
                    if current.weekday() != FRIDAY and (rental_line.id, current) not in existing:
                        commands.append((0, 0, {
                            'contract_line_id': rental_line.id,
                            'equipment_id': rental_line.equipment_id.id,
                            'date': current,
                            'operator_name': rental_line.operator_name,
                            'working_hours': daily_hours,
                        }))
                    current += timedelta(days=1)
            if not commands and not sheet.line_ids:
                raise UserError(_('No machine of %s was on rent during this period.', sheet.contract_id.name))
            if commands:
                sheet.write({'line_ids': commands})

    def action_submit(self):
        for sheet in self:
            if not sheet.line_ids:
                raise UserError(_('Add log lines before sending %s to the client.', sheet.name))
            sheet._portal_ensure_token()
            sheet.state = 'submitted'
            sheet.message_subscribe(partner_ids=sheet.partner_id.ids)
            link = sheet.get_base_url() + sheet.get_portal_url()
            sheet.message_post(
                body=Markup(_(
                    'Equipment log sheet %(name)s for %(start)s to %(end)s is ready for your approval: '
                    '<a href="%(link)s">review and approve online</a>.'
                )) % {'name': sheet.name, 'start': sheet.date_from, 'end': sheet.date_to, 'link': link},
                partner_ids=sheet.partner_id.ids,
                message_type='comment',
                subtype_xmlid='mail.mt_comment',
            )

    def _update_hour_meters(self):
        for sheet in self:
            for equipment in sheet.line_ids.equipment_id:
                readings = sheet.line_ids.filtered(lambda l: l.equipment_id == equipment).mapped('meter_end')
                last = max(readings or [0.0])
                if last > equipment.hour_meter:
                    equipment.sudo().hour_meter = last

    def _portal_set_decision(self, approved, by_name, reason=False):
        """Called from the portal (sudo) or from the back-end."""
        for sheet in self:
            if sheet.state != 'submitted':
                raise UserError(_('Only log sheets waiting for approval can be approved or rejected.'))
            sheet.write({
                'state': 'approved' if approved else 'rejected',
                'approved_by': by_name,
                'approval_date': fields.Datetime.now(),
                'reject_reason': False if approved else reason,
            })
            if approved:
                sheet._update_hour_meters()
                sheet.message_post(body=_('Log sheet approved by %s.', by_name))
            else:
                sheet.message_post(body=_('Log sheet rejected by %(who)s. Reason: %(reason)s',
                                          who=by_name, reason=reason or '-'))
                sheet.activity_schedule(
                    'mail.mail_activity_data_todo',
                    summary=_('Client rejected log sheet %s', sheet.name),
                    user_id=sheet.contract_id.user_id.id or self.env.user.id,
                )

    def action_approve_internal(self):
        self._portal_set_decision(True, self.env.user.name)

    def action_draft(self):
        self.write({'state': 'draft', 'approved_by': False, 'approval_date': False, 'reject_reason': False})
        self.line_ids._check_duplicate_day()

    def action_preview_portal(self):
        self.ensure_one()
        self._portal_ensure_token()
        return {
            'type': 'ir.actions.act_url',
            'target': 'new',
            'url': self.get_portal_url(),
        }


class EquipmentLogsheetLine(models.Model):
    _name = 'dvz.equipment.logsheet.line'
    _description = 'Equipment Log Sheet Line'
    _order = 'date, equipment_id'

    sheet_id = fields.Many2one('dvz.equipment.logsheet', required=True, ondelete='cascade', index=True)
    contract_id = fields.Many2one(related='sheet_id.contract_id', store=True)
    company_id = fields.Many2one(related='sheet_id.company_id', store=True)
    contract_line_id = fields.Many2one(
        'dvz.rental.contract.line', string='Rented Machine', required=True,
        domain="[('contract_id', '=', contract_id)]")
    equipment_id = fields.Many2one(
        'dvz.equipment', string='Equipment', compute='_compute_equipment_id', store=True, readonly=False)
    date = fields.Date(required=True)
    operator_name = fields.Char(string='Operator')
    meter_start = fields.Float(string='Meter Start')
    meter_end = fields.Float(string='Meter End')
    working_hours = fields.Float(string='Working')
    idle_hours = fields.Float(string='Idle / Standby')
    breakdown_hours = fields.Float(string='Breakdown')
    fuel_liters = fields.Float(string='Fuel (L)')
    note = fields.Char()

    @api.depends('contract_line_id')
    def _compute_equipment_id(self):
        for line in self:
            line.equipment_id = line.contract_line_id.equipment_id

    @api.onchange('meter_start', 'meter_end')
    def _onchange_meter(self):
        if self.meter_start and self.meter_end and self.meter_end >= self.meter_start:
            self.working_hours = self.meter_end - self.meter_start

    @api.constrains('meter_start', 'meter_end')
    def _check_meter(self):
        for line in self:
            if line.meter_end and line.meter_end < line.meter_start:
                raise ValidationError(_('Meter end cannot be lower than meter start (%s).', line.date))

    @api.constrains('contract_line_id', 'date')
    def _check_duplicate_day(self):
        for line in self:
            duplicate = self.search([
                ('id', '!=', line.id),
                ('contract_line_id', '=', line.contract_line_id.id),
                ('date', '=', line.date),
                ('sheet_id.state', '!=', 'rejected'),
            ], limit=1)
            if duplicate:
                raise ValidationError(_(
                    '%(equipment)s is already logged on %(date)s in %(sheet)s.',
                    equipment=line.equipment_id.display_name, date=line.date, sheet=duplicate.sheet_id.name))
