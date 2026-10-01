from odoo import _, api, fields, models


class HrEmployee(models.Model):
    _inherit = 'hr.employee'

    dv_assignment_ids = fields.One2many('dvz.manpower.assignment', 'employee_id', string='Supply Assignments')
    dv_current_contract_id = fields.Many2one(
        'dvz.manpower.contract', string='Current Supply Contract',
        compute='_compute_dv_current_assignment')
    dv_current_client_id = fields.Many2one(
        'res.partner', string='Current Client', compute='_compute_dv_current_assignment')
    dv_assignment_count = fields.Integer(compute='_compute_dv_current_assignment')

    @api.depends('dv_assignment_ids.state')
    def _compute_dv_current_assignment(self):
        for employee in self:
            active = employee.dv_assignment_ids.filtered(lambda a: a.state == 'active')[:1]
            employee.dv_current_contract_id = active.contract_id
            employee.dv_current_client_id = active.partner_id
            employee.dv_assignment_count = len(employee.dv_assignment_ids)

    def action_dv_view_assignments(self):
        self.ensure_one()
        return {
            'type': 'ir.actions.act_window',
            'name': _('Supply Assignments'),
            'res_model': 'dvz.manpower.assignment',
            'view_mode': 'list,form',
            'domain': [('employee_id', '=', self.id)],
            'context': {'default_employee_id': self.id},
        }
