from odoo import _, api, fields, models


class Equipment(models.Model):
    _inherit = 'dvz.equipment'

    service_interval = fields.Float(
        string='Service Interval (h)', default=250.0,
        help='Preventive service every X engine hours. Set 0 to disable service alerts.')
    last_service_meter = fields.Float(string='Last Service at (h)', tracking=True)
    last_service_date = fields.Date(string='Last Service Date')
    next_service_meter = fields.Float(string='Next Service at (h)', compute='_compute_service_status', store=True)
    hours_to_service = fields.Float(string='Hours to Service', compute='_compute_service_status', store=True)
    service_status = fields.Selection([
        ('ok', 'OK'),
        ('due_soon', 'Due Soon'),
        ('overdue', 'Overdue'),
        ('none', 'No Plan'),
    ], compute='_compute_service_status', store=True, string='Service Status')
    service_ids = fields.One2many('dvz.equipment.service', 'equipment_id', string='Service Log')
    service_count = fields.Integer(compute='_compute_service_count')
    maintenance_cost = fields.Monetary(
        compute='_compute_service_count', currency_field='currency_id', string='Maintenance Cost')
    document_ids = fields.One2many('dvz.equipment.document', 'equipment_id', string='Documents')
    document_alert = fields.Boolean(compute='_compute_document_alert', string='Document Alert')

    @api.depends('service_interval', 'last_service_meter', 'hour_meter', 'company_id.dv_eq_service_alert_hours')
    def _compute_service_status(self):
        for equipment in self:
            if not equipment.service_interval:
                equipment.next_service_meter = 0.0
                equipment.hours_to_service = 0.0
                equipment.service_status = 'none'
                continue
            equipment.next_service_meter = equipment.last_service_meter + equipment.service_interval
            equipment.hours_to_service = equipment.next_service_meter - equipment.hour_meter
            alert = equipment.company_id.dv_eq_service_alert_hours or 25.0
            if equipment.hours_to_service < 0:
                equipment.service_status = 'overdue'
            elif equipment.hours_to_service <= alert:
                equipment.service_status = 'due_soon'
            else:
                equipment.service_status = 'ok'

    @api.depends('service_ids.cost', 'service_ids.state')
    def _compute_service_count(self):
        for equipment in self:
            services = equipment.service_ids.filtered(lambda s: s.state != 'cancelled')
            equipment.service_count = len(services)
            equipment.maintenance_cost = sum(services.mapped('cost'))

    @api.depends('document_ids.status')
    def _compute_document_alert(self):
        for equipment in self:
            equipment.document_alert = any(s in ('expiring', 'expired') for s in equipment.document_ids.mapped('status'))

    @api.model_create_multi
    def create(self, vals_list):
        # a new machine starts its service plan from its current hour meter
        for vals in vals_list:
            if not vals.get('last_service_meter') and vals.get('hour_meter'):
                vals['last_service_meter'] = vals['hour_meter']
        return super().create(vals_list)

    def action_view_services(self):
        self.ensure_one()
        return {
            'type': 'ir.actions.act_window',
            'name': _('Service Log'),
            'res_model': 'dvz.equipment.service',
            'view_mode': 'list,form',
            'domain': [('equipment_id', '=', self.id)],
            'context': {'default_equipment_id': self.id},
        }

    @api.model
    def _cron_check_service_due(self):
        machines = self.search([('service_status', 'in', ('due_soon', 'overdue'))])
        todo_type = self.env.ref('mail.mail_activity_data_todo', raise_if_not_found=False)
        for equipment in machines:
            if equipment.activity_ids.filtered(lambda a: a.activity_type_id == todo_type):
                continue
            equipment.activity_schedule(
                'mail.mail_activity_data_todo',
                summary=_('Service due: %s', equipment.display_name),
                note=_('Next service at %(next)s h, hour meter is now %(now)s h.',
                       next=equipment.next_service_meter, now=equipment.hour_meter),
                user_id=(equipment.current_contract_id.user_id
                         or self.env.ref('base.user_admin', raise_if_not_found=False)
                         or self.env.user).id,
            )
