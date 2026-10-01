{
    'name': 'Manpower Timesheets & Client Portal Approval (KSA)',
    'version': '19.0.1.0.0',
    'category': 'Human Resources',
    'summary': 'Monthly worker timesheets per client contract with days, hours and overtime. '
               'Clients approve or reject timesheets online in the Odoo portal.',
    'description': """
Manpower Timesheets & Client Portal Approval
============================================
Add-on for Manpower Supply Contracts (KSA):

* One timesheet per contract and period (e.g. monthly)
* Auto-fill lines from active worker assignments (Friday excluded by default)
* Days worked, regular hours and overtime per worker
* Send to client: the client approves or rejects in the customer portal
* Full approval history in the chatter
""",
    'author': 'DigitalVizta',
    'website': 'https://digitalvizta.net',
    'support': 'info@digitalvizta.net',
    'license': 'OPL-1',
    'price': 79.0,
    'currency': 'USD',
    'depends': ['dv_manpower_supply', 'portal'],
    'data': [
        'security/ir.model.access.csv',
        'security/timesheet_security.xml',
        'data/ir_sequence_data.xml',
        'views/manpower_timesheet_views.xml',
        'views/manpower_contract_views.xml',
        'views/portal_templates.xml',
    ],
    'images': ['static/description/banner.png'],
    'installable': True,
    'application': False,
}
