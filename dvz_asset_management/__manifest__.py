# -*- coding: utf-8 -*-

{
    'name': 'Asset Management',
    'version': '16.0.1',
    'category': 'custom',
    'summary': 'Asset Management',
    'license':'LGPL-3',
    'price' : 15.0,
    'currency': 'USD',
    'description': """
     Asset management is a simple system to manage assets owned by an organization.
""",
    'author' : 'DigitalVizta',
    'website' : '',
    'depends': ['base','mail'],
    'images': ['static/description/odoo.png'],
    'data': [
         'security/security.xml',
         'security/ir.model.access.csv',
         'views/asset_sequence.xml',
         'views/asset_view.xml',
         'views/asset_move_view.xml'
             
             ],

    'installable': True,
    'application': True,
    'auto_install': False,
}


