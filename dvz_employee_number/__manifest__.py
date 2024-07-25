# -*- coding: utf-8 -*-
##############################################################################

##############################################################################

{
    'name': 'Employee Number',
    'version': '1.0',
    'sequence': 1,
    'category': 'Generic Modules/Human Resources',
    'description':
        """
This Module add below functionality into odoo

        1.This module helps you to display unique Employee Number on Employee screen

    """,
    'summary': 'Odoo app will add Employee Number on Employee screen',
    "author": "digitalvizta",
    "website" : "https://digitalvizta.com/",
    'depends': ['hr','hr_contract'],
    'data': [
        'views/employee_sequence.xml',
        'views/employee_view.xml'
    ],
    'demo': [],
    'test': [],
    'css': [],
    'qweb': [],
    'js': [],
    'installable': True,
    'application': True,
    'auto_install': False,
    'license': 'LGPL-3',
    'images': ['static/description/odoo.png'],
    
    #author and support Details ==========#
    'pre_init_hook' :'pre_init_check',
}

