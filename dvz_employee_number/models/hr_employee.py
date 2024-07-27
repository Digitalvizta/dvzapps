# -*- coding: utf-8 -*-
##############################################################################

##############################################################################

from odoo import models, fields, api, _


class HrEmployee(models.Model):
    _inherit = 'hr.employee'

    emp_seq = fields.Char("Employee Sequence", required=True, readonly=True, copy=False, default='/')
    
    @api.model
    def create(self, vals):
        if vals.get('emp_seq',  '/') == '/':
            vals['emp_seq'] = self.env['ir.sequence'].next_by_code(
                'hr.employee') or '/'
        return super(HrEmployee, self).create(vals)
        
        
    def copy(self, default=None):
        if default is None:
            default = {}
        default['emp_seq'] = '/'
        return super(HrEmployee, self).copy(default=default)

    @api.model
    def generate_employee_sequences(self):
        employees = self.search([('emp_seq', '=', '/')])
        sequence = 1
        for employee in employees:
            employee.emp_seq = f'EMP{sequence:04d}'
            sequence += 1
        return True


        
        
    
