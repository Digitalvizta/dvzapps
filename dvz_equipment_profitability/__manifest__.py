{
    'name': 'Equipment Rental Profitability (Profit per Machine & Client)',
    'version': '19.0.1.0.0',
    'category': 'Services',
    'summary': 'Real profit of every machine, rental and client: ownership cost, operator cost, fuel and '
               'maintenance against rental revenue. Pivot and graph analysis for managers.',
    'description': """
Equipment Rental Profitability
==============================
Add-on for Equipment Rental Billing and Equipment Maintenance:

* Monthly ownership cost (depreciation / finance / lease) and operator cost per machine
* Fuel cost from log sheet litres when fuel is supplied by you
* Cost, profit and margin on every log sheet day
* Profit per machine including maintenance and repair cost
* Pivot and graph by machine, category, client, rental or month
* "Loss-making" filter, cost and profit visible to Equipment Rental managers only
""",
    'author': 'DigitalVizta',
    'website': 'https://digitalvizta.net',
    'support': 'info@digitalvizta.net',
    'license': 'OPL-1',
    'price': 49.0,
    'currency': 'USD',
    'depends': ['dvz_equipment_rental_billing', 'dvz_equipment_maintenance'],
    'data': [
        'views/equipment_views.xml',
        'views/profitability_views.xml',
        'views/res_config_settings_views.xml',
    ],
    'images': ['static/description/banner.png'],
    'installable': True,
    'application': False,
}
