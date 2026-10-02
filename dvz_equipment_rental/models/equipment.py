from odoo import _, api, fields, models

RATE_TYPES = [
    ('hour', 'Per Hour'),
    ('day', 'Per Day'),
    ('week', 'Per Week'),
    ('month', 'Per Month'),
]


class EquipmentCategory(models.Model):
    _name = 'dvz.equipment.category'
    _description = 'Equipment Category'
    _order = 'name'

    name = fields.Char(required=True, translate=True)
    code = fields.Char()
    color = fields.Integer()
    company_id = fields.Many2one('res.company')
    equipment_ids = fields.One2many('dvz.equipment', 'category_id')
    equipment_count = fields.Integer(compute='_compute_equipment_count')

    def _compute_equipment_count(self):
        for category in self:
            category.equipment_count = len(category.equipment_ids)


class Equipment(models.Model):
    _name = 'dvz.equipment'
    _description = 'Rental Equipment'
    _inherit = ['mail.thread', 'mail.activity.mixin']
    _order = 'code, name'
    _rec_names_search = ['name', 'code', 'plate_number', 'serial_number']

    name = fields.Char(string='Equipment', required=True, tracking=True)
    code = fields.Char(string='Asset No.', tracking=True, copy=False)
    active = fields.Boolean(default=True)
    image_128 = fields.Image(string='Photo', max_width=128, max_height=128)
    color = fields.Integer()
    category_id = fields.Many2one('dvz.equipment.category', string='Category', tracking=True, index=True)
    make = fields.Char(string='Make / Brand')
    model_name = fields.Char(string='Model')
    year = fields.Integer(string='Year')
    serial_number = fields.Char(string='Serial / Chassis No.', copy=False)
    plate_number = fields.Char(string='Plate No.', copy=False, tracking=True)
    capacity = fields.Char(string='Capacity', help='e.g. 50 ton, 1.2 m3 bucket, 500 kVA')
    hour_meter = fields.Float(string='Hour Meter', tracking=True, help='Current engine hours / odometer reading.')
    company_id = fields.Many2one('res.company', required=True, default=lambda self: self.env.company, index=True)
    currency_id = fields.Many2one(related='company_id.currency_id')
    rate_hour = fields.Monetary(string='Rate per Hour', currency_field='currency_id')
    rate_day = fields.Monetary(string='Rate per Day', currency_field='currency_id')
    rate_week = fields.Monetary(string='Rate per Week', currency_field='currency_id')
    rate_month = fields.Monetary(string='Rate per Month', currency_field='currency_id')
    state = fields.Selection([
        ('available', 'Available'),
        ('on_rent', 'On Rent'),
        ('maintenance', 'In Maintenance'),
        ('retired', 'Retired'),
    ], default='available', required=True, tracking=True, copy=False)
    rental_line_ids = fields.One2many('dvz.rental.contract.line', 'equipment_id', string='Rental History')
    current_partner_id = fields.Many2one(
        'res.partner', string='Current Client', compute='_compute_current_rental')
    current_contract_id = fields.Many2one(
        'dvz.rental.contract', string='Current Contract', compute='_compute_current_rental')
    rental_count = fields.Integer(compute='_compute_current_rental')
    notes = fields.Html()

    _code_company_uniq = models.Constraint(
        'unique(code, company_id)', 'The asset number must be unique per company.')

    @api.depends('rental_line_ids.contract_state')
    def _compute_current_rental(self):
        for equipment in self:
            current = equipment.rental_line_ids.filtered(lambda l: l.contract_state == 'on_rent')[:1]
            equipment.current_contract_id = current.contract_id
            equipment.current_partner_id = current.contract_id.partner_id
            equipment.rental_count = len(equipment.rental_line_ids.contract_id)

    @api.depends('code', 'name')
    def _compute_display_name(self):
        for equipment in self:
            equipment.display_name = '[%s] %s' % (equipment.code, equipment.name) if equipment.code else equipment.name

    def _get_rate(self, rate_type):
        self.ensure_one()
        return {
            'hour': self.rate_hour,
            'day': self.rate_day,
            'week': self.rate_week,
            'month': self.rate_month,
        }.get(rate_type, 0.0)

    def action_set_maintenance(self):
        self.write({'state': 'maintenance'})

    def action_set_available(self):
        self.write({'state': 'available'})

    def action_retire(self):
        self.write({'state': 'retired', 'active': False})

    def action_view_rentals(self):
        self.ensure_one()
        return {
            'type': 'ir.actions.act_window',
            'name': _('Rentals'),
            'res_model': 'dvz.rental.contract',
            'view_mode': 'list,form',
            'domain': [('id', 'in', self.rental_line_ids.contract_id.ids)],
        }
