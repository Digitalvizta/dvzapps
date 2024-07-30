# -*- coding: utf-8 -*-

{
    "name" : "Sales Commission from Sales/Invoice/Payment in Odoo ",
    "version" : "16.0.0.1",
    'category' : "Sales",
    'license':'LGPL-3',
    'images': ['static/description/odoo.png'],
    "summary" : "Sale Commission for sales order invoice based commission payment based commission margin based commission for product margin commissions for sales person commission for partner Sales Agent commission Sales Commission for Users commission based on margin",
    "description": """
    
    """,
    "author" : "DigitalVizta",
    "website" : "",
    "price": 30,
    "currency": 'EUR',
    "depends" : ['base' , 'sale', 'sale_management', 'sale_stock', 'sale_margin'],
    "data" :[
        'security/sales_commission_security.xml',
        'security/ir.model.access.csv',
        'account/account_invoice_view.xml',
        'commission_view.xml',
        'base/res/res_partner_view.xml',
        'sale/sale_config_settings.xml',
        'sale/sale_view.xml',

    ],
    "auto_install": False,
    "installable": True,
}

