# -*- coding: utf-8 -*-

from odoo import models, fields, api

import threading

from datetime import date
from dateutil.relativedelta import relativedelta

from odoo import api, fields, models, _
from odoo.exceptions import ValidationError

from odoo.osv import expression

import logging
_logger = logging.getLogger(__name__)
class payroll_income_tax_slabs(models.Model):
    _name = 'dvz_payroll_income_tax_slabs.dvz_payroll_income_tax_slabs'
    _description = 'dvz_payroll_income_tax_slabs.dvz_payroll_income_tax_slabs'
    relation_field=fields.One2many("hr.employee",'hr_linked_fields')
    yearly_start_limit=fields.Float("Year Start Limit")
    yearly_end_limit = fields.Float("Year End Limit")
    deduction_type = fields.Selection([
        ("by_percentage","By Percentage"),
        ("fixed_amount","Fixed Amount"),
    ])
    amount=fields.Float("Amount")

class InheritEmployee(models.Model):
    _inherit = 'hr.employee'
    hr_linked_fields=fields.Many2one("dvz_payroll_income_tax_slabs.dvz_payroll_income_tax_slabs")

class HrContract(models.Model):
    _inherit = 'hr.contract'


    income_tax=fields.Float(string="Income Tax",readonly=True)

    @api.onchange('wage')
    def validate_mail(self):
        if self.wage:
           search_records=self.env['dvz_payroll_income_tax_slabs.dvz_payroll_income_tax_slabs'].search([])
           for all_records in search_records:
               if self.wage>=all_records.yearly_start_limit and self.wage<=all_records.yearly_end_limit:
                   self.income_tax=all_records.amount/100*self.wage
    def write(self, vals):
        if vals.get('wage'):
            search_records = self.env['dvz_payroll_income_tax_slabs.dvz_payroll_income_tax_slabs'].search([])
            for all_records in search_records:
                if vals.get('wage') >= all_records.yearly_start_limit and vals.get('wage') <= all_records.yearly_end_limit:
                    vals['income_tax'] = all_records.amount / 100 * vals.get('wage')
        old_state = {c.id: c.state for c in self}
        res = super(HrContract, self).write(vals)
        new_state = {c.id: c.state for c in self}
        if vals.get('state') == 'open':
            self._assign_open_contract()
        today = fields.Date.today()
        for contract in self:
            if contract == contract.employee_id.contract_id \
                and old_state[contract.id] == 'open' \
                and new_state[contract.id] != 'open':
                running_contract = self.env['hr.contract'].search([
                    ('employee_id', '=', contract.employee_id.id),
                    ('company_id', '=', contract.company_id.id),
                    ('state', '=', 'open'),
                ]).filtered(lambda c: c.date_start <= today and (not c.date_end or c.date_end >= today))
                if running_contract:
                    contract.employee_id.contract_id = running_contract[0]
        if vals.get('state') == 'close':
            for contract in self.filtered(lambda c: not c.date_end):
                contract.date_end = max(date.today(), contract.date_start)
        date_end = vals.get('date_end')
        if self.env.context.get('close_contract', True) and date_end and fields.Date.from_string(date_end) < fields.Date.context_today(self):
            for contract in self.filtered(lambda c: c.state == 'open'):
                contract.state = 'close'

        calendar = vals.get('resource_calendar_id')
        if calendar:
            self.filtered(lambda c: c.state == 'open' or (c.state == 'draft' and c.kanban_state == 'done')).mapped('employee_id').write({'resource_calendar_id': calendar})

        if 'state' in vals and 'kanban_state' not in vals:
            self.write({'kanban_state': 'normal'})

        return res
