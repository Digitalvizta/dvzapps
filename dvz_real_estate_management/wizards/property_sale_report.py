# -*- coding: utf-8 -*-

from odoo import fields, models


class PropertySaleReport(models.TransientModel):
    """A class for the transient model property.sale.report"""
    _name = 'property.sale.report'
    _description = 'Property Sale Report'

    from_date = fields.Date(string="From Date",
                            help='Records from the date will be selected')
    to_date = fields.Date(string="To Date",
                          help='Records till the date will be selected')
    property_id = fields.Many2one('property.property', string="Property Name",
                                  help='The property will be selected')
    partner_id = fields.Many2one('res.partner', string="Customer",
                                 help='The Customer will be selected')

    def action_create_report(self):
        """The function executes query related to the datas given
        and returns a pdf report"""
        query = """ select a.name as customer,b.name,x.create_date,x.state 
                                    from property_sale x
                                    join res_partner a on partner_id = a.id 
                                    join property_property b 
                                    on x.property_id = b.id"""
        if self.partner_id:
            query += """ and a.name = '%s'""" % self.partner_id.name
        if self.property_id:
            query += """ and b.name = '%s'""" % self.property_id.name
        if self.from_date:
            query += """ and x.create_date > '%s'""" % self.from_date
        if self.to_date:
            query += """ and x.create_date < '%s'""" % self.to_date
        self._cr.execute(query)
        datas = self.env.cr.dictfetchall()
        data = {
            'datas': datas,
            'to_date': self.to_date,
            'from_date': self.from_date,
            'partner_name': self.partner_id.name,
            'property_name': self.property_id.name,
        }
        return self.env.ref(
            'dvz_real_estate_management.property_sale_report_action_report').report_action(
            self, data=data)