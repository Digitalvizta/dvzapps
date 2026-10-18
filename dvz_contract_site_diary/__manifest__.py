{
    'name': 'Site Diary: Daily Site Reports for Contractors',
    'summary': 'Daily site report per contract: manpower, equipment, work done, weather, delays, safety and photos, '
               'approved by the site engineer. Labour and equipment hours flow into job costing.',
    'description': 'Part of the DigitalVizta Contracting Suite. The site engineer records each day on site; on '
                   'approval, labour and equipment costs are posted to the contract per BOQ item. Delays are '
                   'logged with hours lost and who is responsible, ready for extension-of-time claims.',
    'version': '19.0.1.0.0',
    'category': 'Services/Contracting',
    'author': 'DigitalVizta',
    'website': 'https://digitalvizta.net/construction-erp/?utm_source=odoo_apps&utm_medium=app_store&utm_campaign=dvz_contract_site_diary',
    'support': 'info@digitalvizta.net',
    'license': 'OPL-1',
    'depends': ['dvz_contract_costing'],
    'data': [
        'security/security.xml',
        'security/ir.model.access.csv',
        'data/sequence.xml',
        'views/dvz_site_diary_views.xml',
        'views/dvz_contract_views.xml',
        'views/res_config_settings_views.xml',
        'views/menus.xml',
        'report/site_diary_report.xml',
    ],
    'images': ['static/description/banner.png'],
    'installable': True,
    'price': 99.0,
    'currency': 'USD',
}
