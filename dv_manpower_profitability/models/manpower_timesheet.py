from odoo import api, fields, models


class ManpowerTimesheetLine(models.Model):
    _inherit = 'dv.manpower.timesheet.line'

    partner_id = fields.Many2one(related='sheet_id.partner_id', store=True, string='Client')
    date_from = fields.Date(related='sheet_id.date_from', store=True, string='Period Start')
    sheet_state = fields.Selection(related='sheet_id.state', store=True, string='Timesheet Status')
    amount_cost = fields.Monetary(
        string='Cost', compute='_compute_profit', store=True, currency_field='currency_id', groups='dv_manpower_supply.group_manpower_manager')
    amount_profit = fields.Monetary(
        string='Profit', compute='_compute_profit', store=True, currency_field='currency_id', groups='dv_manpower_supply.group_manpower_manager')
    margin_percent = fields.Float(
        string='Margin %', compute='_compute_profit', store=True, aggregator='avg', groups='dv_manpower_supply.group_manpower_manager')

    @api.depends('amount_total', 'days_worked', 'employee_id.dv_total_monthly_cost',
                 'sheet_id.date_from', 'sheet_id.date_to')
    def _compute_profit(self):
        for line in self:
            sheet = line.sheet_id
            period_days = sheet._count_working_days(sheet.date_from, sheet.date_to) \
                if sheet.date_from and sheet.date_to else 0
            period_days = period_days or 26
            monthly_cost = line.employee_id.sudo().dv_total_monthly_cost
            ratio = min(line.days_worked / period_days, 1.0) if period_days else 0.0
            line.amount_cost = monthly_cost * ratio
            line.amount_profit = line.amount_total - line.amount_cost
            line.margin_percent = (line.amount_profit / line.amount_total * 100.0) if line.amount_total else 0.0


class ManpowerTimesheet(models.Model):
    _inherit = 'dv.manpower.timesheet'

    amount_cost = fields.Monetary(compute='_compute_profit_totals', store=True, currency_field='currency_id', groups='dv_manpower_supply.group_manpower_manager')
    amount_profit = fields.Monetary(compute='_compute_profit_totals', store=True, currency_field='currency_id', groups='dv_manpower_supply.group_manpower_manager')

    @api.depends('line_ids.amount_cost', 'line_ids.amount_profit')
    def _compute_profit_totals(self):
        for sheet in self:
            sheet.amount_cost = sum(sheet.line_ids.mapped('amount_cost'))
            sheet.amount_profit = sum(sheet.line_ids.mapped('amount_profit'))
