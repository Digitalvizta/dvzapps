# -*- coding: utf-8 -*-

from odoo import models, fields, api
class hr_employee(models.Model):
    _inherit = 'hr.employee'
    def show_all_contratc(self):
        self.ensure_one()
        action = self.env["ir.actions.actions"]._for_xml_id('hr_contract.hr_contract_history_view_list_action')
        action['res_id'] = self.id
        return action
