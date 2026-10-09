{
    'name': 'Contract Cash Flow Forecast',
    'summary': 'Monthly cash in and cash out per project: open invoices, planned billing, retention, subcontractors and purchases.',
    'description': 'Builds a monthly cash flow forecast for every contract and for the whole company from open client '
                   'invoices, approved and planned progress billing, retention releases, subcontractor certificates, '
                   'open purchase orders and the remaining cost budget.',
    'version': '19.0.1.0.0',
    'category': 'Services/Contracting',
    'author': 'DigitalVizta',
    'website': 'https://digitalvizta.net',
    'support': 'info@digitalvizta.net',
    'license': 'OPL-1',
    'depends': ['dvz_contract_ipc', 'dvz_contract_retention', 'dvz_contract_subcontract', 'dvz_contract_procurement'],
    'data': [
        'security/security.xml',
        'security/ir.model.access.csv',
        'data/cron.xml',
        'views/dvz_cashflow_views.xml',
        'views/res_config_settings_views.xml',
    ],
    'images': ['static/description/banner.png'],
    'installable': True,
    'price': 99.0,
    'currency': 'USD',
}
