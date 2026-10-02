from odoo import _, api, fields, models
from odoo.exceptions import UserError, ValidationError

from .equipment import RATE_TYPES

BOOKED_STATES = ('confirmed', 'on_rent')


class RentalContract(models.Model):
    _name = 'dvz.rental.contract'
    _description = 'Equipment Rental Contract'
    _inherit = ['mail.thread', 'mail.activity.mixin']
    _order = 'date_start desc, id desc'

    name = fields.Char(
        string='Rental Reference', required=True, copy=False, readonly=True,
        default=lambda self: _('New'), tracking=True)
    client_reference = fields.Char(string='Client PO / Reference', tracking=True)
    partner_id = fields.Many2one('res.partner', string='Client', required=True, tracking=True, index=True)
    user_id = fields.Many2one(
        'res.users', string='Rental Manager', default=lambda self: self.env.user, tracking=True)
    company_id = fields.Many2one(
        'res.company', required=True, default=lambda self: self.env.company, index=True)
    currency_id = fields.Many2one(related='company_id.currency_id', store=True)
    site = fields.Char(string='Project / Site', tracking=True)
    date_start = fields.Date(string='Start Date', required=True, default=fields.Date.context_today, tracking=True)
    date_end = fields.Date(string='Expected Return', tracking=True)
    state = fields.Selection([
        ('draft', 'Quotation'),
        ('confirmed', 'Reserved'),
        ('on_rent', 'On Rent'),
        ('returned', 'Returned'),
        ('cancelled', 'Cancelled'),
    ], default='draft', required=True, tracking=True, copy=False)
    line_ids = fields.One2many('dvz.rental.contract.line', 'contract_id', string='Equipment', copy=True)
    mobilization_fee = fields.Monetary(
        string='Mobilization Fee', currency_field='currency_id',
        help='One-time charge for transporting the equipment to site (low-bed, crane, permits).')
    demobilization_fee = fields.Monetary(
        string='Demobilization Fee', currency_field='currency_id',
        help='One-time charge for bringing the equipment back from site.')
    equipment_count = fields.Integer(compute='_compute_equipment_count', store=True)
    is_overdue = fields.Boolean(compute='_compute_is_overdue', search='_search_is_overdue')
    notes = fields.Html(string='Terms & Notes')

    @api.depends('line_ids')
    def _compute_equipment_count(self):
        for contract in self:
            contract.equipment_count = len(contract.line_ids)

    def _compute_is_overdue(self):
        today = fields.Date.context_today(self)
        for contract in self:
            contract.is_overdue = bool(
                contract.state == 'on_rent' and contract.date_end and contract.date_end < today)

    def _search_is_overdue(self, operator, value):
        if operator != 'in':
            return NotImplemented
        if True not in value:
            return [(0, '=', 1)]
        today = fields.Date.context_today(self)
        return [('state', '=', 'on_rent'), ('date_end', '!=', False), ('date_end', '<', today)]

    @api.constrains('date_start', 'date_end')
    def _check_dates(self):
        for contract in self:
            if contract.date_end and contract.date_end < contract.date_start:
                raise ValidationError(_('The expected return date cannot be before the start date.'))

    @api.model_create_multi
    def create(self, vals_list):
        for vals in vals_list:
            if vals.get('name', _('New')) == _('New'):
                vals['name'] = self.env['ir.sequence'].next_by_code('dvz.rental.contract') or _('New')
        return super().create(vals_list)

    def write(self, vals):
        old_dates = {c.id: (c.date_start, c.date_end) for c in self} if {'date_start', 'date_end'} & set(vals) else {}
        res = super().write(vals)
        for contract in self.filtered(lambda c: c.id in old_dates and c.state in ('draft', 'confirmed', 'on_rent')):
            old_start, old_end = old_dates[contract.id]
            for line in contract.line_ids:
                line_vals = {}
                if 'date_start' in vals and contract.state != 'on_rent' and line.date_from == old_start:
                    line_vals['date_from'] = contract.date_start
                if 'date_end' in vals and line.date_to == old_end:
                    line_vals['date_to'] = contract.date_end
                if line_vals:
                    line.write(line_vals)
        return res

    # ------------------------------------------------------------------ actions
    def action_confirm(self):
        for contract in self:
            if not contract.line_ids:
                raise UserError(_('Add at least one machine before confirming %s.', contract.name))
            unavailable = contract.line_ids.equipment_id.filtered(lambda e: e.state in ('maintenance', 'retired'))
            if unavailable:
                raise UserError(_('These machines are not available for rent: %s',
                                  ', '.join(unavailable.mapped('display_name'))))
        self.write({'state': 'confirmed'})
        # re-run the double booking check now that the lines are booked
        self.line_ids._check_double_booking()

    def _check_before_dispatch(self):
        """Hook for add-ons (e.g. block machines with expired insurance or inspection)."""
        return True

    def action_dispatch(self):
        today = fields.Date.context_today(self)
        for contract in self:
            if contract.state != 'confirmed':
                raise UserError(_('Only reserved rentals can be dispatched.'))
            contract._check_before_dispatch()
            busy = contract.line_ids.equipment_id.filtered(lambda e: e.state in ('on_rent', 'maintenance', 'retired'))
            if busy:
                raise UserError(_('These machines are on rent elsewhere, in maintenance or retired: %s',
                                  ', '.join(busy.mapped('display_name'))))
            for line in contract.line_ids:
                # the rental starts on the real dispatch date
                vals = {'date_from': today}
                if line.date_to and line.date_to < today:
                    vals['date_to'] = False
                if not line.meter_out:
                    vals['meter_out'] = line.equipment_id.hour_meter
                line.write(vals)
            contract.line_ids.equipment_id.write({'state': 'on_rent'})
            contract.write({'state': 'on_rent'})
            contract.message_post(body=_('Equipment dispatched to site.'))

    def action_return(self):
        today = fields.Date.context_today(self)
        for contract in self:
            if contract.state != 'on_rent':
                raise UserError(_('Only rentals on rent can be returned.'))
            for line in contract.line_ids:
                # the rental ends on the real return date (earlier or later than planned)
                line.write({'date_to': max(today, line.date_from) if line.date_from else today})
                if line.meter_in and line.meter_in > line.equipment_id.hour_meter:
                    line.equipment_id.hour_meter = line.meter_in
            contract.line_ids.equipment_id.filtered(lambda e: e.state == 'on_rent').write({'state': 'available'})
            contract.write({'state': 'returned'})
            contract.activity_ids.filtered(lambda a: a.summary and contract.name in a.summary).action_done()
            contract.message_post(body=_('Equipment returned from site.'))

    def action_cancel(self):
        for contract in self:
            if contract.state == 'on_rent':
                raise UserError(_('Return the equipment of %s before cancelling it.', contract.name))
        self.write({'state': 'cancelled'})

    def action_draft(self):
        self.write({'state': 'draft'})

    @api.model
    def _cron_overdue_returns(self):
        overdue = self.search([('is_overdue', '=', True)])
        todo = self.env.ref('mail.mail_activity_data_todo', raise_if_not_found=False)
        for contract in overdue:
            if contract.activity_ids.filtered(lambda a: a.activity_type_id == todo):
                continue
            contract.activity_schedule(
                'mail.mail_activity_data_todo',
                summary=_('Return overdue: %s', contract.name),
                note=_('Expected return was %(date)s. Extend the rental or collect the equipment from %(site)s.',
                       date=contract.date_end, site=contract.site or contract.partner_id.name),
                user_id=contract.user_id.id or self.env.user.id,
            )


class RentalContractLine(models.Model):
    _name = 'dvz.rental.contract.line'
    _description = 'Rented Equipment Line'
    _order = 'sequence, id'
    _rec_name = 'equipment_id'

    sequence = fields.Integer(default=10)
    contract_id = fields.Many2one('dvz.rental.contract', required=True, ondelete='cascade', index=True)
    contract_state = fields.Selection(related='contract_id.state', store=True, string='Rental Status')
    partner_id = fields.Many2one(related='contract_id.partner_id', store=True, string='Client')
    company_id = fields.Many2one(related='contract_id.company_id', store=True)
    currency_id = fields.Many2one(related='contract_id.currency_id')
    equipment_id = fields.Many2one(
        'dvz.equipment', string='Equipment', required=True, index=True,
        domain="[('state', '!=', 'retired'), ('company_id', '=', company_id)]")
    category_id = fields.Many2one(related='equipment_id.category_id', store=True)
    rate_type = fields.Selection(RATE_TYPES, default='month', required=True)
    rate = fields.Monetary(
        compute='_compute_rate', store=True, readonly=False, currency_field='currency_id')
    with_operator = fields.Boolean(string='With Operator', default=True)
    operator_name = fields.Char(string='Operator')
    date_from = fields.Date(
        string='From', compute='_compute_dates', store=True, readonly=False, precompute=True)
    date_to = fields.Date(
        string='To', compute='_compute_dates', store=True, readonly=False, precompute=True)
    meter_out = fields.Float(string='Meter Out')
    meter_in = fields.Float(string='Meter In')
    meter_used = fields.Float(string='Hours Used', compute='_compute_meter_used', store=True)

    @api.depends('equipment_id', 'rate_type')
    def _compute_rate(self):
        for line in self:
            if line.equipment_id:
                line.rate = line.equipment_id._get_rate(line.rate_type)

    @api.depends('contract_id.date_start', 'contract_id.date_end')
    def _compute_dates(self):
        for line in self:
            if not line.date_from:
                line.date_from = line.contract_id.date_start
            if not line.date_to:
                line.date_to = line.contract_id.date_end

    @api.depends('meter_out', 'meter_in')
    def _compute_meter_used(self):
        for line in self:
            line.meter_used = max(line.meter_in - line.meter_out, 0.0) if line.meter_in else 0.0

    @api.constrains('date_from', 'date_to')
    def _check_line_dates(self):
        for line in self:
            if line.date_from and line.date_to and line.date_to < line.date_from:
                raise ValidationError(_('The "To" date cannot be before the "From" date.'))

    @api.constrains('equipment_id', 'date_from', 'date_to', 'contract_state')
    def _check_double_booking(self):
        for line in self.filtered(lambda l: l.contract_state in BOOKED_STATES and l.date_from):
            domain = [
                ('id', '!=', line.id),
                ('equipment_id', '=', line.equipment_id.id),
                ('contract_state', 'in', BOOKED_STATES),
                '|', ('date_to', '=', False), ('date_to', '>=', line.date_from),
            ]
            if line.date_to:
                domain += [('date_from', '<=', line.date_to)]
            clash = self.search(domain, limit=1)
            if clash:
                raise ValidationError(_(
                    '%(equipment)s is already booked on %(contract)s (%(client)s) for overlapping dates.',
                    equipment=line.equipment_id.display_name, contract=clash.contract_id.name,
                    client=clash.partner_id.name))
