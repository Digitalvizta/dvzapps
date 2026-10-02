{
    'name': 'Equipment Rental Billing from Log Sheets (ZATCA)',
    'version': '19.0.1.0.0',
    'category': 'Services',
    'summary': 'Turn client-approved equipment log sheets into customer invoices in one click: hourly, daily, '
               'weekly and monthly rates, extra hours, minimum hours, mobilization and demobilization. ZATCA ready.',
    'description': """
Equipment Rental Billing from Log Sheets
========================================
Add-on for Equipment Log Sheets:

* Automatic amounts from the rate on each rented machine (hour, day, week or month)
* Monthly rates prorated on the working days of the month (Fridays excluded)
* Extra hours above the daily standard billed with your factor
* Breakdown days are not billed, standby (idle) days are
* Minimum guaranteed hours for hourly rentals
* Mobilization and demobilization fees invoiced once
* One-click and bulk invoicing, standard Odoo invoices (ZATCA e-invoicing with the Saudi localization)
""",
    'author': 'DigitalVizta',
    'website': 'https://digitalvizta.net',
    'support': 'info@digitalvizta.net',
    'license': 'OPL-1',
    'price': 79.0,
    'currency': 'USD',
    'depends': ['dvz_equipment_logsheet', 'account'],
    'data': [
        'data/product_data.xml',
        'views/equipment_logsheet_views.xml',
        'views/rental_contract_views.xml',
    ],
    'images': ['static/description/banner.png'],
    'installable': True,
    'application': False,
}
