from odoo import api, fields, models

MANAGER = 'dvz_equipment_rental.group_equipment_manager'


class RentalContract(models.Model):
    _inherit = 'dvz.rental.contract'

    profit_revenue = fields.Monetary(compute='_compute_profit', currency_field='currency_id', groups=MANAGER,
                                     string='Revenue')
    profit_cost = fields.Monetary(compute='_compute_profit', currency_field='currency_id', groups=MANAGER,
                                  string='Cost')
    profit_amount = fields.Monetary(compute='_compute_profit', currency_field='currency_id', groups=MANAGER,
                                    string='Profit')
    profit_margin = fields.Float(compute='_compute_profit', groups=MANAGER, string='Margin %')

    @api.depends('logsheet_ids.state', 'logsheet_ids.amount_total')
    def _compute_profit(self):
        for contract in self:
            lines = contract.sudo().logsheet_ids.filtered(lambda s: s.state == 'approved').line_ids
            revenue = sum(lines.mapped('amount_total')) + (
                contract.mobilization_fee if contract.mobilization_invoiced else 0.0) + (
                contract.demobilization_fee if contract.demobilization_invoiced else 0.0)
            cost = sum(lines.mapped('amount_cost'))
            contract.profit_revenue = revenue
            contract.profit_cost = cost
            contract.profit_amount = revenue - cost
            contract.profit_margin = (revenue - cost) / revenue * 100.0 if revenue else 0.0


class RentalContractLine(models.Model):
    _inherit = 'dvz.rental.contract.line'

    fuel_by_owner = fields.Boolean(
        string='Fuel by Us', help='Tick when you supply the fuel: litres on log sheets are costed.')
