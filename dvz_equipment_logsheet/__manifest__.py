{
    'name': 'Equipment Log Sheets & Client Portal Approval',
    'version': '19.0.1.0.0',
    'category': 'Services',
    'summary': 'Daily equipment log sheets per rental: working, idle and breakdown hours, hour meter and fuel. '
               'Clients approve or reject the monthly log sheet online in the Odoo portal.',
    'description': """
Equipment Log Sheets & Client Portal Approval
=============================================
Add-on for Equipment Rental (Heavy Equipment & Fleet):

* One log sheet per rental and period (e.g. monthly)
* One click to fill a line per machine per working day (Friday excluded)
* Hour meter start / end, working, idle (standby) and breakdown hours, fuel and operator
* Send to client: the site engineer approves or rejects online in the customer portal
* Approved readings update the hour meter of each machine
* Full approval history in the chatter
""",
    'author': 'DigitalVizta',
    'website': 'https://digitalvizta.net',
    'support': 'info@digitalvizta.net',
    'license': 'OPL-1',
    'price': 79.0,
    'currency': 'USD',
    'depends': ['dvz_equipment_rental', 'portal'],
    'data': [
        'security/ir.model.access.csv',
        'security/logsheet_security.xml',
        'data/ir_sequence_data.xml',
        'views/equipment_logsheet_views.xml',
        'views/rental_contract_views.xml',
        'views/portal_templates.xml',
    ],
    'images': ['static/description/banner.png'],
    'installable': True,
    'application': False,
}
