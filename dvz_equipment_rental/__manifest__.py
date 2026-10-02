{
    'name': 'Equipment Rental (Heavy Equipment & Fleet)',
    'version': '19.0.1.0.0',
    'category': 'Services',
    'summary': 'Rent out cranes, excavators, loaders, trucks and generators: equipment register, '
               'rental contracts with hourly / daily / weekly / monthly rates, dispatch and return, '
               'no double booking and a rental schedule.',
    'description': """
Equipment Rental for Construction & Heavy Equipment Companies
=============================================================
Free base app for equipment rental companies (KSA, GCC, Pakistan and worldwide):

* Equipment register: asset number, category, make, model, year, serial / chassis,
  plate number, capacity and hour meter
* Default rates per hour, day, week and month on each machine
* Rental contracts with client, site, period, mobilization and demobilization fees
* With or without operator on each rented machine
* Dispatch and return with hour meter out / in
* No double booking: a machine cannot be rented twice for overlapping dates
* Rental schedule (calendar) and overdue return alerts
* Multi-company, Arabic / English ready
""",
    'author': 'DigitalVizta',
    'website': 'https://digitalvizta.net',
    'support': 'info@digitalvizta.net',
    'license': 'LGPL-3',
    'depends': ['mail'],
    'data': [
        'security/equipment_security.xml',
        'security/ir.model.access.csv',
        'data/ir_sequence_data.xml',
        'data/ir_cron_data.xml',
        'data/equipment_category_data.xml',
        'views/equipment_views.xml',
        'views/rental_contract_views.xml',
        'views/res_config_settings_views.xml',
        'views/menus.xml',
    ],
    'images': ['static/description/banner.png'],
    'installable': True,
    'application': True,
}
