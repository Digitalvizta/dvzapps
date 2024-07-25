# -*- coding: utf-8 -*-
{
    'name': "dvz_contract_list",
    'summary': """
        Contract List""",

    'description': """
        Contract List
    """,
    'category': "HR",
    "author": "digitalvizta",
    "website" : "https://digitalvizta.com/",
    # any module necessary for this one to work correctly
    'depends': ['base','hr','hr_contract'],

    # always loaded
    'data': [
        # 'security/ir.model.access.csv',
        'views/views.xml',
        'views/templates.xml',
    ],
    # only loaded in demonstration mode
    'demo': [
        'demo/demo.xml',
    ],
    "auto_install": False,
    "installable": True,
    'images': ['static/description/odoo.png'],
}