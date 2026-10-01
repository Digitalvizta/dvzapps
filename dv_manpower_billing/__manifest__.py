{
    'name': 'Manpower Billing: Invoices from Timesheets (KSA, ZATCA)',
    'version': '19.0.1.0.0',
    'category': 'Accounting/Accounting',
    'summary': 'Turn client-approved manpower timesheets into customer invoices automatically: '
               'hourly, daily or monthly rates plus overtime. Works with Saudi ZATCA e-invoicing.',
    'description': """
Manpower Billing from Timesheets
================================
Add-on for Manpower Supply Contracts (KSA):

* Amount per worker computed from the contract rate (hour / day / month)
* Overtime billed with the configurable factor (default 1.5)
* One-click invoice from an approved timesheet, or bulk invoicing
* Invoices are standard Odoo invoices, so Saudi localization and ZATCA
  e-invoicing (l10n_sa) apply automatically
* Invoice links on the contract and the timesheet
""",
    'author': 'DigitalVizta',
    'website': 'https://digitalvizta.net',
    'support': 'info@digitalvizta.net',
    'license': 'OPL-1',
    'price': 79.0,
    'currency': 'USD',
    'depends': ['dv_manpower_timesheet', 'account'],
    'data': [
        'data/product_data.xml',
        'views/manpower_timesheet_views.xml',
        'views/manpower_contract_views.xml',
    ],
    'images': ['static/description/banner.png'],
    'installable': True,
    'application': False,
}
