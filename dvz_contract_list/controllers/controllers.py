# -*- coding: utf-8 -*-
# from odoo import http


# class DvzContractList(http.Controller):
#     @http.route('/dvz_contract_list/dvz_contract_list', auth='public')
#     def index(self, **kw):
#         return "Hello, world"

#     @http.route('/dvz_contract_list/dvz_contract_list/objects', auth='public')
#     def list(self, **kw):
#         return http.request.render('dvz_contract_list.listing', {
#             'root': '/dvz_contract_list/dvz_contract_list',
#             'objects': http.request.env['dvz_contract_list.dvz_contract_list'].search([]),
#         })

#     @http.route('/dvz_contract_list/dvz_contract_list/objects/<model("dvz_contract_list.dvz_contract_list"):obj>', auth='public')
#     def object(self, obj, **kw):
#         return http.request.render('dvz_contract_list.object', {
#             'object': obj
#         })
