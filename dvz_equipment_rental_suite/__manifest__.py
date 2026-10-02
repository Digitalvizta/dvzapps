{
    'name': 'Equipment Rental Suite for Construction & Heavy Equipment Companies',
    'version': '19.0.1.0.0',
    'category': 'Services',
    'summary': 'All-in-one for heavy equipment rental: rental contracts and schedule, client-approved log sheets, '
               'ZATCA invoicing, maintenance and document expiry, and profit per machine.',
    'description': """
Bundle of the DigitalVizta Equipment Rental Suite. Installs:

* Equipment Rental (free core)
* Equipment Log Sheets & Client Portal Approval
* Equipment Rental Billing from Log Sheets (ZATCA)
* Equipment Maintenance, Service Plans & Document Expiry
* Equipment Rental Profitability

Works on Odoo 19 Community and Enterprise.
""",
    'author': 'DigitalVizta',
    'website': 'https://digitalvizta.net',
    'support': 'info@digitalvizta.net',
    'license': 'OPL-1',
    'depends': [
        'dvz_equipment_rental',
        'dvz_equipment_logsheet',
        'dvz_equipment_rental_billing',
        'dvz_equipment_maintenance',
        'dvz_equipment_profitability',
    ],
    'data': [],
    'images': ['static/description/banner.png'],
    'installable': True,
    'application': True,
}
