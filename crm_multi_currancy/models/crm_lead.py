# -*- coding: utf-8 -*-

from odoo import models, fields, api

class CrmLead(models.Model):
    _inherit = "crm.lead"

    from_currency_id = fields.Many2one('res.currency', string="From Currency",default=lambda self: self.env.company.currency_id)

    expected_revenue = fields.Monetary(string="Expected Revenue", currency_field="from_currency_id")

    to_currency_id = fields.Many2one('res.currency',string="To Currency",  default=lambda self: self.env.ref('base.EUR'), required=True)

    converted_amount = fields.Monetary(string="Converted Amount", compute="_compute_converted_amount", currency_field="to_currency_id")


    @api.depends('expected_revenue', 'from_currency_id', 'to_currency_id')
    def _compute_converted_amount(self):
        for lead in self:
            if lead.expected_revenue and lead.from_currency_id and lead.to_currency_id:
                lead.converted_amount = lead.from_currency_id._convert(
                    lead.expected_revenue,
                    lead.to_currency_id,
                    lead.company_id,
                    fields.Date.today()
                )
            else:
                lead.converted_amount = 0.0

