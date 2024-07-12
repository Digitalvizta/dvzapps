# -*- coding: utf-8 -*-
# from odoo import http


# class PayrollIncomeTaxSlabs(http.Controller):
#     @http.route('/dvz_payroll_income_tax_slabs/dvz_payroll_income_tax_slabs', auth='public')
#     def index(self, **kw):
#         return "Hello, world"

#     @http.route('/dvz_payroll_income_tax_slabs/dvz_payroll_income_tax_slabs/objects', auth='public')
#     def list(self, **kw):
#         return http.request.render('dvz_payroll_income_tax_slabs.listing', {
#             'root': '/dvz_payroll_income_tax_slabs/dvz_payroll_income_tax_slabs',
#             'objects': http.request.env['dvz_payroll_income_tax_slabs.dvz_payroll_income_tax_slabs'].search([]),
#         })

#     @http.route('/dvz_payroll_income_tax_slabs/dvz_payroll_income_tax_slabs/objects/<model("dvz_payroll_income_tax_slabs.dvz_payroll_income_tax_slabs"):obj>', auth='public')
#     def object(self, obj, **kw):
#         return http.request.render('dvz_payroll_income_tax_slabs.object', {
#             'object': obj
#         })
