{
    'name': 'Manpower Supply Suite for Saudi Manpower Companies',
    'version': '19.0.1.0.0',
    'category': 'Human Resources',
    'summary': 'All-in-one for KSA manpower supply companies: contracts, worker documents and Ajeer alerts, '
               'client-approved timesheets, ZATCA invoicing and profit per worker.',
    'description': """
Bundle of the DigitalVizta Manpower Supply Suite. Installs:

* Manpower Supply Contracts (free core)
* Worker Documents & Ajeer Expiry Alerts
* Manpower Timesheets & Client Portal Approval
* Manpower Billing from Timesheets (ZATCA)
* Manpower Profitability

Works on Odoo 19 Community and Enterprise.
""",
    'author': 'DigitalVizta',
    'website': 'https://digitalvizta.net',
    'support': 'info@digitalvizta.net',
    'license': 'OPL-1',
    'depends': [
        'dvz_manpower_supply',
        'dvz_manpower_documents',
        'dvz_manpower_timesheet',
        'dvz_manpower_billing',
        'dvz_manpower_profitability',
    ],
    'data': [],
    'images': ['static/description/banner.png'],
    'installable': True,
    'application': True,
}
