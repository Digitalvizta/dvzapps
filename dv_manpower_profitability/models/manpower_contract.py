from odoo import fields, models


class ManpowerContract(models.Model):
    _inherit = 'dv.manpower.contract'

    profit_revenue = fields.Monetary(string='Revenue', compute='_compute_profitability', currency_field='currency_id', groups='dv_manpower_supply.group_manpower_manager')
    profit_cost = fields.Monetary(string='Cost', compute='_compute_profitability', currency_field='currency_id', groups='dv_manpower_supply.group_manpower_manager')
    profit_amount = fields.Monetary(string='Profit', compute='_compute_profitability', currency_field='currency_id', groups='dv_manpower_supply.group_manpower_manager')
    profit_margin = fields.Float(string='Margin %', compute='_compute_profitability', groups='dv_manpower_supply.group_manpower_manager')

    def _compute_profitability(self):
        for contract in self:
            sheets = contract.timesheet_ids.filtered(lambda s: s.state == 'approved')
            contract.profit_revenue = sum(sheets.mapped('amount_total'))
            contract.profit_cost = sum(sheets.mapped('amount_cost'))
            contract.profit_amount = contract.profit_revenue - contract.profit_cost
            contract.profit_margin = (contract.profit_amount / contract.profit_revenue * 100.0) \
                if contract.profit_revenue else 0.0
