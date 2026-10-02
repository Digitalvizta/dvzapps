from odoo import api, fields, models

MANAGER = 'dvz_equipment_rental.group_equipment_manager'


class Equipment(models.Model):
    _inherit = 'dvz.equipment'

    ownership_cost_month = fields.Monetary(
        string='Ownership Cost / Month', currency_field='currency_id', groups=MANAGER,
        help='Depreciation, finance or lease instalment, insurance and registration per month.')
    operator_cost_month = fields.Monetary(
        string='Operator Cost / Month', currency_field='currency_id', groups=MANAGER,
        help='Salary, GOSI, housing and allowances of the operator, used when rented with operator.')
    profit_revenue = fields.Monetary(
        string='Rental Revenue', compute='_compute_profit', currency_field='currency_id', groups=MANAGER)
    profit_cost = fields.Monetary(
        string='Operating Cost', compute='_compute_profit', currency_field='currency_id', groups=MANAGER)
    profit_amount = fields.Monetary(
        string='Net Profit', compute='_compute_profit', currency_field='currency_id', groups=MANAGER,
        help='Revenue of approved log sheets minus ownership, operator, fuel and maintenance cost.')
    profit_margin = fields.Float(string='Margin %', compute='_compute_profit', groups=MANAGER)

    @api.depends('maintenance_cost')
    def _compute_profit(self):
        Line = self.env['dvz.equipment.logsheet.line'].sudo()
        groups = Line._read_group(
            [('equipment_id', 'in', self.ids), ('sheet_state', '=', 'approved')],
            ['equipment_id'], ['amount_total:sum', 'amount_cost:sum'])
        data = {equipment.id: (revenue, cost) for equipment, revenue, cost in groups}
        for equipment in self:
            revenue, cost = data.get(equipment.id, (0.0, 0.0))
            cost += equipment.maintenance_cost
            equipment.profit_revenue = revenue
            equipment.profit_cost = cost
            equipment.profit_amount = revenue - cost
            equipment.profit_margin = (revenue - cost) / revenue * 100.0 if revenue else 0.0
