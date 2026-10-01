{
    'name': 'Manpower Supply Contracts (KSA)',
    'version': '19.0.1.0.0',
    'category': 'Human Resources',
    'summary': 'Manage manpower supply contracts, client rates and worker assignments '
               'for Saudi manpower / labor supply companies (Ajeer secondment).',
    'description': """
Manpower Supply Contracts for Saudi Arabia
==========================================
Free base app for manpower supply / labor outsourcing companies:

* Client supply contracts with job positions, quantities and rates
  (per hour, per day or per month)
* Worker assignment to clients and sites, with full history
* Automatic expiry of contracts after the end date
* Arabic / English ready, multi-company
""",
    'author': 'DigitalVizta',
    'website': 'https://digitalvizta.net',
    'support': 'info@digitalvizta.net',
    'license': 'LGPL-3',
    'depends': ['hr', 'mail'],
    'data': [
        'security/manpower_security.xml',
        'security/ir.model.access.csv',
        'data/ir_sequence_data.xml',
        'data/ir_cron_data.xml',
        'views/manpower_contract_views.xml',
        'views/manpower_assignment_views.xml',
        'views/hr_employee_views.xml',
        'views/res_config_settings_views.xml',
        'views/menus.xml',
    ],
    'images': ['static/description/banner.png'],
    'installable': True,
    'application': True,
}
