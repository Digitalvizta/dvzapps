{
    'name': 'Contract Procurement & Budget Control',
    'summary': 'Material requests against BOQ items, purchase orders per contract and budget vs actual per BOQ item.',
    'description': 'Site teams raise material requests against BOQ items. Approved requests become RFQs and purchase '
                   'orders linked to the contract. Every BOQ item shows its cost budget against requested, ordered, '
                   'received and billed amounts, with an over-budget warning or block on purchase orders.',
    'version': '19.0.1.0.0',
    'category': 'Services/Contracting',
    'author': 'DigitalVizta',
    'website': 'https://digitalvizta.net',
    'support': 'info@digitalvizta.net',
    'license': 'OPL-1',
    'depends': ['dvz_contract', 'purchase'],
    'data': [
        'security/security.xml',
        'security/ir.model.access.csv',
        'data/sequence.xml',
        'views/dvz_material_request_views.xml',
        'views/purchase_order_views.xml',
        'views/dvz_contract_views.xml',
        'views/res_config_settings_views.xml',
        'views/menus.xml',
    ],
    'images': ['static/description/banner.png'],
    'installable': True,
    'price': 129.0,
    'currency': 'USD',
}
