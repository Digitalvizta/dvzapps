{
    'name': 'Tendering & Estimation for Contractors',
    'summary': 'From CRM opportunity to signed contract: priced BOQ tenders on Odoo quotations, cost build-up, '
               'revisions (R0, R1, R2), bilingual tender offer, bid bonds, won/lost and one-click contract.',
    'description': 'Turns the standard Odoo quotation into a construction tender: BOQ items with item numbers and '
                   'units, cost breakdown (material, labour, equipment, subcontract) with overhead and profit, '
                   'calculated rates, locked revisions, a bilingual tender offer by email and portal, bid bonds, '
                   'won/lost tracking on the CRM opportunity, and one click to create the contract with its BOQ '
                   'and cost budget. Tenders never create invoices: billing stays on the contract.',
    'version': '19.0.1.0.0',
    'category': 'Services/Contracting',
    'author': 'DigitalVizta',
    'website': 'https://digitalvizta.net/construction-erp/?utm_source=odoo_apps&utm_medium=app_store&utm_campaign=dvz_contract_tender',
    'support': 'info@digitalvizta.net',
    'license': 'OPL-1',
    'depends': ['sale_crm', 'dvz_contract', 'dvz_contract_retention'],
    'data': [
        'security/ir.model.access.csv',
        'data/product_data.xml',
        'data/sequence.xml',
        'report/tender_report.xml',
        'data/mail_template.xml',
        'wizard/dvz_tender_lost_views.xml',
        'views/sale_order_views.xml',
        'views/crm_lead_views.xml',
        'views/dvz_contract_views.xml',
        'views/res_config_settings_views.xml',
        'views/menus.xml',
    ],
    'images': ['static/description/banner.png'],
    'installable': True,
    'price': 129.0,
    'currency': 'USD',
}
