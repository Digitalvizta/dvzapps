from odoo import api, fields, models

from odoo.addons.dvz_equipment_rental_billing.models.equipment_logsheet import working_days_in_month

MANAGER = 'dvz_equipment_rental.group_equipment_manager'


class EquipmentLogsheetLine(models.Model):
    _inherit = 'dvz.equipment.logsheet.line'

    partner_id = fields.Many2one(related='sheet_id.partner_id', store=True, string='Client')
    category_id = fields.Many2one(related='equipment_id.category_id', store=True, string='Category')
    sheet_state = fields.Selection(related='sheet_id.state', store=True, string='Log Sheet Status')
    amount_cost = fields.Float(string='Cost', compute='_compute_profit', store=True, groups=MANAGER)
    amount_profit = fields.Float(string='Profit', compute='_compute_profit', store=True, groups=MANAGER)
    margin_percent = fields.Float(
        string='Margin %', compute='_compute_profit', store=True, aggregator='avg', groups=MANAGER)

    @api.depends('amount_total', 'date', 'fuel_liters', 'equipment_id.ownership_cost_month',
                 'equipment_id.operator_cost_month', 'contract_line_id.with_operator',
                 'contract_line_id.fuel_by_owner', 'company_id.dv_eq_fuel_price')
    def _compute_profit(self):
        for line in self:
            equipment = line.equipment_id.sudo()
            days = working_days_in_month(line.date) if line.date else 26
            cost = equipment.ownership_cost_month / days
            if line.contract_line_id.with_operator:
                cost += equipment.operator_cost_month / days
            if line.contract_line_id.fuel_by_owner:
                cost += line.fuel_liters * line.company_id.dv_eq_fuel_price
            line.amount_cost = cost
            line.amount_profit = line.amount_total - cost
            line.margin_percent = (line.amount_profit / line.amount_total * 100.0) if line.amount_total else 0.0


class EquipmentLogsheet(models.Model):
    _inherit = 'dvz.equipment.logsheet'

    amount_cost = fields.Monetary(compute='_compute_profit_totals', store=True, currency_field='currency_id',
                                  groups=MANAGER)
    amount_profit = fields.Monetary(compute='_compute_profit_totals', store=True, currency_field='currency_id',
                                    groups=MANAGER)

    @api.depends('line_ids.amount_cost', 'line_ids.amount_profit')
    def _compute_profit_totals(self):
        for sheet in self:
            sheet.amount_cost = sum(sheet.line_ids.mapped('amount_cost'))
            sheet.amount_profit = sum(sheet.line_ids.mapped('amount_profit'))
