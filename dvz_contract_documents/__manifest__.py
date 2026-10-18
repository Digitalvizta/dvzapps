{
    'name': 'Document Control for Contractors: RFIs, Submittals & Transmittals',
    'summary': 'Requests for information, material and shop-drawing submittals with A/B/C/D review codes and '
               'revisions, and document transmittals, answered and reviewed by the consultant in the portal.',
    'description': 'Part of the DigitalVizta Contracting Suite. Track every RFI and submittal per contract with '
                   'due dates and overdue alerts. Consultants answer RFIs, review submittals and acknowledge '
                   'transmittals online; an RFI with cost or time impact becomes a variation order in one click.',
    'version': '19.0.1.0.0',
    'category': 'Services/Contracting',
    'author': 'DigitalVizta',
    'website': 'https://digitalvizta.net/construction-erp/?utm_source=odoo_apps&utm_medium=app_store&utm_campaign=dvz_contract_documents',
    'support': 'info@digitalvizta.net',
    'license': 'OPL-1',
    'depends': ['dvz_contract_portal'],
    'data': [
        'security/security.xml',
        'security/ir.model.access.csv',
        'data/sequence.xml',
        'data/cron.xml',
        'views/dvz_rfi_views.xml',
        'views/dvz_submittal_views.xml',
        'views/dvz_transmittal_views.xml',
        'views/dvz_contract_views.xml',
        'views/res_config_settings_views.xml',
        'views/menus.xml',
        'views/portal_templates.xml',
        'report/transmittal_report.xml',
    ],
    'images': ['static/description/banner.png'],
    'installable': True,
    'price': 99.0,
    'currency': 'USD',
}
