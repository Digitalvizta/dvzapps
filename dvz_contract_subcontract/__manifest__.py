{
    'name': 'Subcontractor Management & Certificates',
    'summary': 'Subcontracts under the main contract, subcontractor certificates and vendor bills.',
    'description': 'Manage subcontracts like client contracts: BOQ, retention, advance and payment certificates on '
                   'the vendor side. Certificates become vendor bills with retention payable and advance recovery.',
    'version': '19.0.1.0.0',
    'category': 'Services/Contracting',
    'author': 'DigitalVizta',
    'website': 'https://digitalvizta.net',
    'support': 'info@digitalvizta.net',
    'license': 'OPL-1',
    'depends': ['dvz_contract_ipc'],
    'data': [
        'data/sequence.xml',
        'views/dvz_subcontract_views.xml',
        'views/res_config_settings_views.xml',
        'views/menus.xml',
    ],
    'installable': True,
    'price': 99.0,
    'currency': 'USD',
}
