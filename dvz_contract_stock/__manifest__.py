{
    'name': 'Site Stores & Material Control for Contractors',
    'summary': 'A store per site, stock-aware material requests, transfers between sites, returns '
               'and material usage per BOQ item. Every feature can be switched on or off.',
    'description': 'Each contract gets its own site store. Material requests take what is available in the main '
                   'store and buy only the shortfall. Material moves between sites and back to the store with its '
                   'cost, so every project shows its real material cost. Site teams record material used and '
                   'wasted per BOQ item. Supplier returns reduce the ordered cost. All features are optional '
                   'and switched on or off in Settings > Contracting > Site Stores.',
    'version': '19.0.1.0.0',
    'category': 'Services/Contracting',
    'author': 'DigitalVizta',
    'website': 'https://digitalvizta.net/construction-erp/?utm_source=odoo_apps&utm_medium=app_store&utm_campaign=dvz_contract_stock',
    'support': 'info@digitalvizta.net',
    'license': 'OPL-1',
    'depends': ['dvz_contract_procurement', 'purchase_stock'],
    'data': [
        'security/security.xml',
        'security/ir.model.access.csv',
        'data/sequence.xml',
        'views/res_config_settings_views.xml',
        'views/dvz_material_usage_views.xml',
        'views/dvz_material_request_views.xml',
        'views/dvz_contract_views.xml',
        'views/stock_views.xml',
        'views/menus.xml',
    ],
    'images': ['static/description/banner.png'],
    'installable': True,
    'price': 129.0,
    'currency': 'USD',
}
