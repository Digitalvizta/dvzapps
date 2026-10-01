{
    'name': 'Manpower Profitability: Profit per Worker & Contract (KSA)',
    'version': '19.0.1.0.0',
    'category': 'Human Resources',
    'summary': 'See the real profit of every supplied worker and client contract: billed amount '
               'minus salary, GOSI, housing, transport and other costs. Pivot and graph analysis.',
    'description': """
Manpower Profitability
======================
Add-on for Manpower Supply Contracts (KSA):

* Monthly cost per worker: salary, GOSI, housing, transport, iqama/visa and other costs
* Cost, profit and margin on every timesheet line (prorated on days worked)
* Profit and margin on every supply contract
* Profitability analysis with pivot and graph by client, contract, worker or job
* Cost fields visible to managers only
""",
    'author': 'DigitalVizta',
    'website': 'https://digitalvizta.net',
    'support': 'info@digitalvizta.net',
    'license': 'OPL-1',
    'price': 49.0,
    'currency': 'USD',
    'depends': ['dv_manpower_billing'],
    'data': [
        'views/hr_employee_views.xml',
        'views/profitability_views.xml',
    ],
    'images': ['static/description/banner.png'],
    'installable': True,
    'application': False,
}
