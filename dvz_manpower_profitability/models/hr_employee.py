from odoo import api, fields, models

MANAGER = 'dvz_manpower_supply.group_manpower_manager'


class HrEmployee(models.Model):
    _inherit = 'hr.employee'

    dv_cost_currency_id = fields.Many2one(related='company_id.currency_id', string='Cost Currency')
    dv_monthly_salary = fields.Monetary(string='Monthly Salary', currency_field='dv_cost_currency_id', groups=MANAGER)
    dv_gosi_cost = fields.Monetary(string='GOSI (employer share)', currency_field='dv_cost_currency_id', groups=MANAGER)
    dv_housing_cost = fields.Monetary(string='Housing', currency_field='dv_cost_currency_id', groups=MANAGER)
    dv_transport_cost = fields.Monetary(string='Transport', currency_field='dv_cost_currency_id', groups=MANAGER)
    dv_iqama_cost = fields.Monetary(
        string='Iqama / Visa / Levy (monthly)', currency_field='dv_cost_currency_id', groups=MANAGER,
        help='Yearly government fees (iqama, work permit levy, insurance) divided by 12.')
    dv_other_cost = fields.Monetary(string='Other Costs', currency_field='dv_cost_currency_id', groups=MANAGER)
    dv_total_monthly_cost = fields.Monetary(
        string='Total Monthly Cost', currency_field='dv_cost_currency_id',
        compute='_compute_dv_total_monthly_cost', store=True, groups=MANAGER)

    @api.depends('dv_monthly_salary', 'dv_gosi_cost', 'dv_housing_cost', 'dv_transport_cost',
                 'dv_iqama_cost', 'dv_other_cost')
    def _compute_dv_total_monthly_cost(self):
        for employee in self:
            employee.dv_total_monthly_cost = (
                employee.dv_monthly_salary + employee.dv_gosi_cost + employee.dv_housing_cost
                + employee.dv_transport_cost + employee.dv_iqama_cost + employee.dv_other_cost)
