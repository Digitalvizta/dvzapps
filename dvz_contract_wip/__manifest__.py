{
    'name': 'Revenue Recognition (WIP) for Contractors: IFRS 15 Percentage of Completion',
    'summary': 'Month-end WIP schedule: percentage of completion per contract, over- and under-billing, '
               'expected-loss provision and the journal entry with automatic reversal.',
    'description': 'Part of the DigitalVizta Contracting Suite. Revenue is recognised as work progresses '
                   '(cost-to-cost, certified progress or entered), not only when certificates are invoiced. '
                   'Each month the WIP run books unbilled revenue (contract asset) or billings in excess '
                   '(contract liability), provides for expected losses and reverses itself the next day.',
    'version': '19.0.1.0.0',
    'category': 'Services/Contracting',
    'author': 'DigitalVizta',
    'website': 'https://digitalvizta.net/construction-erp/?utm_source=odoo_apps&utm_medium=app_store&utm_campaign=dvz_contract_wip',
    'support': 'info@digitalvizta.net',
    'license': 'OPL-1',
    'depends': ['dvz_contract_costing'],
    'data': [
        'security/security.xml',
        'security/ir.model.access.csv',
        'data/sequence.xml',
        'views/dvz_wip_run_views.xml',
        'views/dvz_contract_views.xml',
        'views/res_config_settings_views.xml',
        'views/menus.xml',
        'report/wip_report.xml',
    ],
    'images': ['static/description/banner.png'],
    'installable': True,
    'price': 129.0,
    'currency': 'USD',
}
