# -*- coding: utf-8 -*-
{
    'name': "Payroll Income Tax Slabs",

    'summary': """
        Payroll Summary Tax slabs""",

    'description': """
        Long description of module's purpose
    """,

    "author" : "digitalvizta",
    "website" : "https://digitalvizta.com/",
    'license':'LGPL-3',
    'images': ['static/description/odoo.png'],

    'category': 'payroll',
    "version" : "16.0.0.1",
    "price": 69,
    "currency": 'EUR',
    # any module necessary for this one to work correctly
    'depends': ['base','hr','om_hr_payroll'],

    # always loaded
    'data': [
        'security/ir.model.access.csv',
        'views/views.xml',
        'views/templates.xml',
    ],
    # only loaded in demonstration mode
    'demo': [
        'demo/demo.xml',
    ],
}
