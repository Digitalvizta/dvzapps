from odoo import _, api, fields, models
from odoo.exceptions import UserError, ValidationError

WEATHER = [
    ('sunny', 'Sunny / clear'),
    ('hot', 'Very hot'),
    ('cloudy', 'Cloudy'),
    ('windy', 'Windy'),
    ('sandstorm', 'Sandstorm / dust'),
    ('rain', 'Rain'),
    ('storm', 'Storm'),
    ('cold', 'Cold'),
]


class DvzSiteDiary(models.Model):
    _name = 'dvz.site.diary'
    _description = 'Site Diary (Daily Site Report)'
    _inherit = ['mail.thread', 'mail.activity.mixin']
    _order = 'date desc, id desc'
    _check_company_auto = True

    name = fields.Char('Reference', required=True, copy=False, readonly=True, default=lambda self: _('New'))
    contract_id = fields.Many2one(
        'dvz.contract', 'Contract', required=True, index=True, tracking=True, check_company=True,
        domain="[('contract_type', '=', 'client'), ('state', 'in', ('progress', 'handover'))]")
    project_id = fields.Many2one(related='contract_id.project_id', store=True)
    partner_id = fields.Many2one(related='contract_id.partner_id', store=True, string='Client')
    company_id = fields.Many2one(related='contract_id.company_id', store=True, index=True)
    currency_id = fields.Many2one(related='contract_id.currency_id', store=True)
    date = fields.Date('Date', required=True, default=fields.Date.context_today, tracking=True, index=True)
    shift = fields.Selection([('day', 'Day'), ('night', 'Night')], default='day', required=True)
    engineer_id = fields.Many2one('res.users', 'Site Engineer', default=lambda self: self.env.user, tracking=True)
    state = fields.Selection([('draft', 'Draft'), ('submitted', 'Submitted'), ('approved', 'Approved')],
                             default='draft', required=True, tracking=True, copy=False, index=True)
    approved_by_id = fields.Many2one('res.users', 'Approved By', readonly=True, copy=False)
    approved_date = fields.Datetime('Approved On', readonly=True, copy=False)

    weather = fields.Selection(WEATHER, 'Weather')
    temp_max = fields.Float('Max. Temperature (°C)', digits=(4, 1))
    site_condition = fields.Selection([('normal', 'Normal'), ('restricted', 'Restricted'), ('stopped', 'Work stopped')],
                                      'Site Condition', default='normal')
    work_hours = fields.Float('Site Working Hours', default=10.0, digits=(4, 1))

    manpower_ids = fields.One2many('dvz.site.diary.manpower', 'diary_id', 'Manpower', copy=True)
    equipment_ids = fields.One2many('dvz.site.diary.equipment', 'diary_id', 'Equipment', copy=True)
    work_ids = fields.One2many('dvz.site.diary.work', 'diary_id', 'Work Done')
    delay_ids = fields.One2many('dvz.site.diary.delay', 'diary_id', 'Delays & Issues')
    photo_ids = fields.One2many('dvz.site.diary.photo', 'diary_id', 'Photos')

    toolbox_talk = fields.Boolean('Toolbox talk held')
    incidents = fields.Integer('Incidents / near misses')
    hse_notes = fields.Text('Safety Notes')
    visitors = fields.Text('Visitors & Inspections')
    instructions = fields.Text('Instructions Received', help='Site instructions from the client or consultant.')
    materials_received = fields.Text('Materials Delivered')
    notes = fields.Html('Other Notes')

    manpower_count = fields.Integer('Workers on Site', compute='_compute_totals', store=True)
    labour_hours = fields.Float('Labour Hours', compute='_compute_totals', store=True)
    labour_cost = fields.Monetary('Labour Cost', compute='_compute_totals', store=True)
    equipment_hours = fields.Float('Equipment Hours', compute='_compute_totals', store=True)
    equipment_cost = fields.Monetary('Equipment Cost', compute='_compute_totals', store=True)
    hours_lost = fields.Float('Hours Lost', compute='_compute_totals', store=True)
    photo_count = fields.Integer(compute='_compute_totals', store=True)
    analytic_line_ids = fields.One2many('account.analytic.line', 'dvz_diary_id', 'Posted Costs', readonly=True)

    _diary_uniq = models.Constraint(
        'unique(contract_id, date, shift)', 'There is already a site diary for this contract, date and shift.')

    @api.depends('manpower_ids.headcount', 'manpower_ids.total_hours', 'manpower_ids.cost',
                 'equipment_ids.total_hours', 'equipment_ids.cost', 'delay_ids.hours_lost', 'photo_ids')
    def _compute_totals(self):
        for rec in self:
            rec.manpower_count = sum(rec.manpower_ids.mapped('headcount'))
            rec.labour_hours = sum(rec.manpower_ids.mapped('total_hours'))
            rec.labour_cost = sum(rec.manpower_ids.filtered(lambda l: not l.subcontractor_id).mapped('cost'))
            rec.equipment_hours = sum(rec.equipment_ids.mapped('total_hours'))
            rec.equipment_cost = sum(rec.equipment_ids.mapped('cost'))
            rec.hours_lost = sum(rec.delay_ids.mapped('hours_lost'))
            rec.photo_count = len(rec.photo_ids)

    @api.constrains('date')
    def _check_date(self):
        for rec in self:
            if rec.date and rec.date > fields.Date.context_today(rec):
                raise ValidationError(_('A site diary cannot be for a future date.'))

    @api.model_create_multi
    def create(self, vals_list):
        for vals in vals_list:
            if vals.get('name', _('New')) == _('New'):
                vals['name'] = self.env['ir.sequence'].next_by_code('dvz.site.diary') or _('New')
        return super().create(vals_list)

    def write(self, vals):
        locked = set(vals) - {'state', 'approved_by_id', 'approved_date', 'message_main_attachment_id',
                              'activity_ids', 'message_follower_ids'}
        if locked and not self.env.context.get('dvz_diary_force') and any(r.state == 'approved' for r in self):
            raise UserError(_('An approved site diary cannot be changed. Reset it to draft first.'))
        return super().write(vals)

    def unlink(self):
        if any(rec.state == 'approved' for rec in self):
            raise UserError(_('Reset an approved site diary to draft before deleting it.'))
        return super().unlink()

    # ------------------------------------------------------------------
    def action_copy_previous(self):
        """Fill manpower and equipment from the last diary of the same contract (crews rarely change)."""
        for rec in self:
            if rec.state != 'draft':
                continue
            prev = self.search([('contract_id', '=', rec.contract_id.id), ('id', '!=', rec.id),
                                ('date', '<=', rec.date)], order='date desc, id desc', limit=1)
            if not prev:
                raise UserError(_('There is no earlier site diary for this contract.'))
            rec.write({
                'manpower_ids': [(5, 0, 0)] + [(0, 0, l._copy_vals()) for l in prev.manpower_ids],
                'equipment_ids': [(5, 0, 0)] + [(0, 0, l._copy_vals()) for l in prev.equipment_ids],
                'work_hours': prev.work_hours,
            })
        return True

    def action_submit(self):
        for rec in self:
            if rec.state != 'draft':
                continue
            if not (rec.manpower_ids or rec.equipment_ids or rec.work_ids or rec.delay_ids or rec.notes):
                raise UserError(_('Add manpower, equipment, work done or a note before submitting %s.', rec.name))
            if rec.company_id.dvz_diary_approval:
                rec.state = 'submitted'
                manager = rec.contract_id.user_id
                if manager and manager != self.env.user:
                    rec.activity_schedule('mail.mail_activity_data_todo', user_id=manager.id,
                                          summary=_('Approve site diary %s', rec.name))
            else:
                rec._do_approve()
        return True

    def action_approve(self):
        if not self.env.user.has_group('dvz_contract.group_dvz_contract_manager') \
                and any(rec.contract_id.user_id != self.env.user for rec in self):
            raise UserError(_('Only the contract manager or a contracting manager can approve site diaries.'))
        self.filtered(lambda r: r.state == 'submitted')._do_approve()
        return True

    def _do_approve(self):
        for rec in self:
            rec.with_context(dvz_diary_force=True).write({
                'state': 'approved', 'approved_by_id': self.env.user.id, 'approved_date': fields.Datetime.now()})
            rec._post_costs()
            rec.activity_feedback(['mail.mail_activity_data_todo'])

    def action_draft(self):
        for rec in self:
            rec.analytic_line_ids.sudo().unlink()
            rec.with_context(dvz_diary_force=True).write({'state': 'draft', 'approved_by_id': False,
                                                          'approved_date': False})
        return True

    def _post_costs(self):
        """Labour and equipment cost on the contract's analytic account, per BOQ item."""
        AnalyticLine = self.env['account.analytic.line'].sudo()
        for rec in self:
            contract = rec.contract_id
            column = contract._analytic_column()
            if not column:
                if rec.labour_cost or rec.equipment_cost:
                    rec.message_post(body=_('Costs were not posted: the contract has no analytic account.'))
                continue
            company = rec.company_id
            vals_list = []
            if company.dvz_diary_post_labour:
                for line in rec.manpower_ids.filtered(lambda l: l.cost and not l.subcontractor_id):
                    vals_list.append(rec._cost_vals(line, 'labour', column, line.total_hours,
                                                     '%s: %s' % (rec.name, line.display_name)))
            if company.dvz_diary_post_equipment:
                for line in rec.equipment_ids.filtered('cost'):
                    vals_list.append(rec._cost_vals(line, 'equipment', column, line.total_hours,
                                                     '%s: %s' % (rec.name, line.display_name)))
            if vals_list:
                AnalyticLine.create(vals_list)

    def _cost_vals(self, line, kind, column, hours, label):
        return {
            'name': label,
            'date': self.date,
            'amount': -line.cost,
            'unit_amount': hours,
            'product_id': line.product_id.id,
            'product_uom_id': line.product_id.uom_id.id if line.product_id else False,
            'company_id': self.company_id.id,
            column: self.contract_id.analytic_account_id.id,
            'dvz_contract_line_id': line.contract_line_id.id,
            'dvz_diary_id': self.id,
            'dvz_diary_kind': kind,
            'ref': self.name,
        }


class DvzSiteDiaryLineMixin(models.AbstractModel):
    _name = 'dvz.site.diary.line.mixin'
    _description = 'Site diary line'

    diary_id = fields.Many2one('dvz.site.diary', required=True, ondelete='cascade', index=True)
    contract_id = fields.Many2one(related='diary_id.contract_id', store=True)
    company_id = fields.Many2one(related='diary_id.company_id', store=True)
    currency_id = fields.Many2one(related='diary_id.currency_id')
    date = fields.Date(related='diary_id.date', store=True)
    contract_line_id = fields.Many2one(
        'dvz.contract.line', 'BOQ Item',
        domain="[('contract_id', '=', contract_id), ('display_type', '=', False)]")


class DvzSiteDiaryManpower(models.Model):
    _name = 'dvz.site.diary.manpower'
    _inherit = 'dvz.site.diary.line.mixin'
    _description = 'Site Diary Manpower'

    product_id = fields.Many2one('product.product', 'Trade', required=True,
                                 domain="[('dvz_cost_type', '=', 'labour')]",
                                 help='A labour trade product (e.g. Mason, Steel fixer, Helper) with its hourly cost.')
    employee_id = fields.Many2one('hr.employee', 'Employee', help='Optional: one named person.')
    subcontractor_id = fields.Many2one('res.partner', 'Subcontractor',
                                       help='Crew of a subcontractor: counted for manpower, but not costed '
                                            '(the subcontractor bills you).')
    headcount = fields.Integer('Workers', default=1)
    hours = fields.Float('Hours each', default=8.0, digits=(4, 1))
    overtime = fields.Float('Overtime each', digits=(4, 1))
    rate = fields.Monetary('Rate / Hour')
    total_hours = fields.Float('Total Hours', compute='_compute_cost', store=True)
    cost = fields.Monetary('Cost', compute='_compute_cost', store=True)
    note = fields.Char('Activity')

    @api.depends('headcount', 'hours', 'overtime', 'rate')
    def _compute_cost(self):
        for line in self:
            line.total_hours = line.headcount * (line.hours + line.overtime)
            line.cost = line.total_hours * line.rate

    @api.onchange('product_id', 'employee_id')
    def _onchange_rate(self):
        if self.employee_id and self.employee_id.hourly_cost:
            self.rate = self.employee_id.hourly_cost
            self.headcount = 1
        elif self.product_id:
            self.rate = self.product_id.standard_price

    @api.depends('product_id', 'employee_id', 'headcount', 'subcontractor_id')
    def _compute_display_name(self):
        for line in self:
            who = line.employee_id.name or '%s × %s' % (line.headcount, line.product_id.name or '')
            line.display_name = '%s (%s)' % (who, line.subcontractor_id.name) if line.subcontractor_id else who

    def _copy_vals(self):
        return {f: (self[f].id if hasattr(self[f], 'id') else self[f])
                for f in ('product_id', 'employee_id', 'subcontractor_id', 'headcount', 'hours', 'rate',
                          'contract_line_id', 'note')}


class DvzSiteDiaryEquipment(models.Model):
    _name = 'dvz.site.diary.equipment'
    _inherit = 'dvz.site.diary.line.mixin'
    _description = 'Site Diary Equipment'

    product_id = fields.Many2one('product.product', 'Equipment', required=True,
                                 domain="[('dvz_cost_type', '=', 'equipment')]",
                                 help='An equipment product (e.g. Excavator, Mobile crane) with its hourly cost.')
    quantity = fields.Integer('Units', default=1)
    hours_working = fields.Float('Working Hours each', default=8.0, digits=(4, 1))
    hours_idle = fields.Float('Idle / Breakdown Hours', digits=(4, 1),
                              help='Recorded for delay claims; not costed.')
    rate = fields.Monetary('Rate / Hour')
    ownership = fields.Selection([('own', 'Own'), ('rented', 'Rented')], default='own')
    total_hours = fields.Float('Total Hours', compute='_compute_cost', store=True)
    cost = fields.Monetary('Cost', compute='_compute_cost', store=True)
    note = fields.Char('Activity')

    @api.depends('quantity', 'hours_working', 'rate')
    def _compute_cost(self):
        for line in self:
            line.total_hours = line.quantity * line.hours_working
            line.cost = line.total_hours * line.rate

    @api.onchange('product_id')
    def _onchange_rate(self):
        if self.product_id:
            self.rate = self.product_id.standard_price

    @api.depends('product_id', 'quantity')
    def _compute_display_name(self):
        for line in self:
            line.display_name = '%s × %s' % (line.quantity, line.product_id.name or '')

    def _copy_vals(self):
        return {f: (self[f].id if hasattr(self[f], 'id') else self[f])
                for f in ('product_id', 'quantity', 'hours_working', 'rate', 'ownership', 'contract_line_id', 'note')}


class DvzSiteDiaryWork(models.Model):
    _name = 'dvz.site.diary.work'
    _inherit = 'dvz.site.diary.line.mixin'
    _description = 'Site Diary Work Done'

    contract_line_id = fields.Many2one(required=False)
    description = fields.Char('Work Done', required=True)
    location = fields.Char('Area / Location')
    quantity = fields.Float('Quantity Today', digits='Product Unit')
    uom_id = fields.Many2one(related='contract_line_id.uom_id', string='Unit')
    qty_to_date = fields.Float('Quantity to Date', compute='_compute_qty_to_date', digits='Product Unit',
                               help='Sum of approved site diaries up to this date.')
    percent_to_date = fields.Float('% of BOQ', compute='_compute_qty_to_date')

    @api.onchange('contract_line_id')
    def _onchange_contract_line_id(self):
        if self.contract_line_id and not self.description:
            self.description = (self.contract_line_id.name or '')[:120]

    @api.depends('contract_line_id', 'quantity', 'date')
    def _compute_qty_to_date(self):
        for line in self:
            if not line.contract_line_id:
                line.qty_to_date = line.percent_to_date = 0.0
                continue
            others = self.search([('contract_line_id', '=', line.contract_line_id.id),
                                  ('diary_id.state', '=', 'approved'), ('date', '<=', line.date),
                                  ('id', '!=', line._origin.id or 0)])
            qty = sum(others.mapped('quantity')) + line.quantity
            line.qty_to_date = qty
            line.percent_to_date = qty / line.contract_line_id.quantity * 100.0 if line.contract_line_id.quantity else 0.0


class DvzSiteDiaryDelay(models.Model):
    _name = 'dvz.site.diary.delay'
    _inherit = 'dvz.site.diary.line.mixin'
    _description = 'Site Diary Delay'

    contract_line_id = fields.Many2one(required=False)
    cause = fields.Selection([
        ('weather', 'Weather'),
        ('client', 'Client / owner'),
        ('consultant', 'Consultant approval / drawings'),
        ('material', 'Material shortage'),
        ('equipment', 'Equipment breakdown'),
        ('labour', 'Labour shortage'),
        ('permit', 'Permits / authorities'),
        ('subcontractor', 'Subcontractor'),
        ('utility', 'Utilities / access'),
        ('other', 'Other'),
    ], required=True, default='weather')
    responsible = fields.Selection([('contractor', 'Contractor'), ('client', 'Client / consultant'),
                                   ('neutral', 'Neither (e.g. weather)')], required=True, default='neutral',
                                  help='Client- and neutral delays can support an extension-of-time claim.')
    hours_lost = fields.Float('Hours Lost', digits=(4, 1))
    description = fields.Char('What happened', required=True)


class DvzSiteDiaryPhoto(models.Model):
    _name = 'dvz.site.diary.photo'
    _description = 'Site Diary Photo'
    _order = 'sequence, id'

    diary_id = fields.Many2one('dvz.site.diary', required=True, ondelete='cascade', index=True)
    sequence = fields.Integer(default=10)
    image = fields.Image('Photo', required=True, max_width=1600, max_height=1600)
    caption = fields.Char('Caption')
