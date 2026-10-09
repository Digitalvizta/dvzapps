{
    'name': 'Contract Portal: Consultant & Client Approvals',
    'summary': 'Consultants approve or reject payment certificates and variation orders online; clients follow their '
               'contracts, certificates and variations in the portal.',
    'description': 'Adds a contracting section to the Odoo portal. Consultants (the engineer) review measured '
                   'quantities and approve or reject certificates and variation orders with a comment. Every '
                   'decision is logged with name and time on the document.',
    'version': '19.0.1.0.0',
    'category': 'Services/Contracting',
    'author': 'DigitalVizta',
    'website': 'https://digitalvizta.net',
    'support': 'info@digitalvizta.net',
    'license': 'OPL-1',
    'depends': ['portal', 'dvz_contract_ipc', 'dvz_contract_variation'],
    'data': [
        'views/dvz_contract_views.xml',
        'views/portal_templates.xml',
    ],
    'images': ['static/description/banner.png'],
    'installable': True,
    'price': 99.0,
    'currency': 'USD',
}
