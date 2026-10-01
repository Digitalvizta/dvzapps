{
    'name': 'Worker Documents & Ajeer Expiry Alerts (KSA)',
    'version': '19.0.1.0.0',
    'category': 'Human Resources',
    'summary': 'Track Iqama, passport, Ajeer permit, medical and insurance expiry for '
               'supplied workers, with automatic alerts before they expire.',
    'description': """
Worker Documents & Ajeer Expiry Alerts
======================================
Add-on for Manpower Supply Contracts (KSA):

* Iqama, passport, Ajeer permit, medical, insurance and driving licence records
* Link Ajeer permits to the client supply contract
* Valid / Expiring soon / Expired status, updated every day
* Automatic to-do activities X days before expiry (configurable)
* Warning on the worker assignment when documents are expired
""",
    'author': 'DigitalVizta',
    'website': 'https://digitalvizta.net',
    'support': 'info@digitalvizta.net',
    'license': 'OPL-1',
    'price': 49.0,
    'currency': 'USD',
    'depends': ['dv_manpower_supply'],
    'data': [
        'security/ir.model.access.csv',
        'data/ir_cron_data.xml',
        'views/worker_document_views.xml',
        'views/res_config_settings_views.xml',
    ],
    'images': ['static/description/banner.png'],
    'installable': True,
    'application': False,
}
