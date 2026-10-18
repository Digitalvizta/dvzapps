{
    'name': 'Contracting Management Dashboard',
    'summary': 'One screen for management: contract value, billing, receivables, margin, retention, guarantees, '
               'approvals and the 6-month cash flow across all projects.',
    'description': 'Management dashboard for the DigitalVizta Contracting Suite.',
    'version': '19.0.1.0.0',
    'category': 'Services/Contracting',
    'author': 'DigitalVizta',
    'website': 'https://digitalvizta.net/construction-erp/?utm_source=odoo_apps&utm_medium=app_store&utm_campaign=dvz_contract_dashboard',
    'support': 'info@digitalvizta.net',
    'license': 'OPL-1',
    'depends': ['dvz_contract_ipc', 'dvz_contract_retention', 'dvz_contract_variation', 'dvz_contract_subcontract',
                'dvz_contract_procurement', 'dvz_contract_cashflow'],
    'data': [
        'views/dashboard_views.xml',
    ],
    'assets': {
        'web.assets_backend': [
            'dvz_contract_dashboard/static/src/**/*',
        ],
    },
    'images': ['static/description/banner.png'],
    'installable': True,
    'price': 99.0,
    'currency': 'USD',
}
