from odoo import _, api, fields, models
from odoo.exceptions import UserError


class EquipmentService(models.Model):
    _name = 'dvz.equipment.service'
    _description = 'Equipment Service / Repair'
    _inherit = ['mail.thread', 'mail.activity.mixin']
    _order = 'date desc, id desc'

    name = fields.Char(string='Description', required=True, tracking=True)
    equipment_id = fields.Many2one('dvz.equipment', string='Equipment', required=True, index=True, tracking=True)
    category_id = fields.Many2one(related='equipment_id.category_id', store=True)
    company_id = fields.Many2one(related='equipment_id.company_id', store=True)
    currency_id = fields.Many2one(related='company_id.currency_id')
    service_type = fields.Selection([
        ('preventive', 'Preventive Service'),
        ('breakdown', 'Breakdown'),
        ('repair', 'Repair'),
        ('inspection', 'Inspection'),
    ], required=True, default='preventive', tracking=True)
    date = fields.Date(required=True, default=fields.Date.context_today, tracking=True)
    date_done = fields.Date(string='Completed On', readonly=True, copy=False)
    meter_reading = fields.Float(string='Hour Meter at Service')
    vendor_id = fields.Many2one('res.partner', string='Workshop / Vendor')
    technician = fields.Char()
    cost = fields.Monetary(currency_field='currency_id', tracking=True)
    downtime_hours = fields.Float(string='Downtime (h)')
    state = fields.Selection([
        ('open', 'In Progress'),
        ('done', 'Done'),
        ('cancelled', 'Cancelled'),
    ], default='open', required=True, tracking=True, copy=False)
    notes = fields.Html()

    @api.onchange('equipment_id')
    def _onchange_equipment_id(self):
        if self.equipment_id and not self.meter_reading:
            self.meter_reading = self.equipment_id.hour_meter

    @api.model_create_multi
    def create(self, vals_list):
        services = super().create(vals_list)
        to_shop = services.filtered(lambda s: s.state == 'open' and s.equipment_id.state == 'available')
        to_shop.equipment_id.write({'state': 'maintenance'})
        return services

    def action_done(self):
        for service in self:
            if service.state != 'open':
                raise UserError(_('Only open jobs can be completed.'))
            vals = {}
            if service.meter_reading > service.equipment_id.hour_meter:
                vals['hour_meter'] = service.meter_reading
            if service.service_type == 'preventive':
                vals['last_service_meter'] = service.meter_reading or service.equipment_id.hour_meter
                vals['last_service_date'] = service.date
            other_open = service.equipment_id.service_ids.filtered(
                lambda s: s.state == 'open' and s != service)
            if service.equipment_id.state == 'maintenance' and not other_open:
                vals['state'] = 'available'
            if vals:
                service.equipment_id.write(vals)
            service.write({'state': 'done', 'date_done': fields.Date.context_today(self)})

    def _release_machines(self, equipment):
        """Put machines back in service when they have no other open job."""
        for machine in equipment.filtered(lambda e: e.state == 'maintenance'):
            if not machine.service_ids.filtered(lambda s: s.state == 'open' and s not in self):
                machine.state = 'available'

    def action_cancel(self):
        open_jobs = self.filtered(lambda s: s.state == 'open')
        self.write({'state': 'cancelled'})
        open_jobs._release_machines(open_jobs.equipment_id)

    def action_reopen(self):
        self.write({'state': 'open', 'date_done': False})
        self.equipment_id.filtered(lambda e: e.state == 'available').write({'state': 'maintenance'})

    def unlink(self):
        open_jobs = self.filtered(lambda s: s.state == 'open')
        equipment = open_jobs.equipment_id
        open_jobs._release_machines(equipment)
        return super().unlink()
