{
    'name': 'Job Costing for Contractors: Material, Labour, Equipment, Subcontract & Overheads',
    'summary': 'Cost per BOQ item split into material, labour, equipment, subcontract, site and head-office '
               'overheads, with cost to complete, forecast at completion and final margin.',
    'description': 'Part of the DigitalVizta Contracting Suite. Every cost posted on a contract is classified by '
                   'cost type and BOQ item: vendor bills, site store issues, timesheets, subcontractor '
                   'certificates and head-office overhead allocations. Budgets can be split per BOQ item, and '
                   'the contract shows budget, actual, committed, cost to complete, forecast and margin.',
    'version': '19.0.1.0.0',
    'category': 'Services/Contracting',
    'author': 'DigitalVizta',
    'website': 'https://digitalvizta.net/construction-erp/?utm_source=odoo_apps&utm_medium=app_store&utm_campaign=dvz_contract_costing',
    'support': 'info@digitalvizta.net',
    'license': 'OPL-1',
    'depends': ['dvz_contract_procurement', 'dvz_contract_ipc', 'hr_timesheet'],
    'data': [
        'security/ir.model.access.csv',
        'security/security.xml',
        'data/sequence.xml',
        'views/dvz_contract_views.xml',
        'views/product_views.xml',
        'views/analytic_views.xml',
        'views/dvz_overhead_allocation_views.xml',
        'views/dvz_job_cost_report_views.xml',
        'views/res_config_settings_views.xml',
        'views/menus.xml',
        'report/job_cost_report.xml',
    ],
    'post_init_hook': '_dvz_costing_post_init',
    'images': ['static/description/banner.png'],
    'installable': True,
    'price': 149.0,
    'currency': 'USD',
}
