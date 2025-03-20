# -*- coding: utf-8 -*-
{
    'name': "CRM Multi-Currency",
    'summary': "Manage Expected Revenue in Multiple Currencies within CRM",
    'description': """
        This module extends CRM Leads to support multi-currency expected revenue conversion.
        - Allows defining "From Currency" and "To Currency"
        - Converts Expected Revenue into the selected currency
        - Displays the Converted Amount in the CRM Leads
    """,
    'author': "DigitalVizta",
    'website': "https://www.digitalvizta.com",
    'category': 'Sales/CRM',
    'version': '1.0',

    # Dependencies required for this module
    'depends': ['base', 'crm'],

    # Data files that are always loaded
    'data': [
        'views/crm_lead_view.xml',       # CRM Lead form & kanban modifications
    ],

    'installable': True,
    'application': False,
}
