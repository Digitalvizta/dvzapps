# -*- coding: utf-8 -*-
################################################################################
#
#    Kolpolok Ltd. (https://www.kolpolok.com)
#    Author: Kaushik Ahmed Apu, Aqil Mahmud, Zarin Tasnim(<https://www.kolpolok.com>)
#
################################################################################
{
    'name': "Real Estate Management System",
    'version': '16.0.1.0',
    'sequence': 1,
    'summary': """
        Real estate system manages viewing, brochures, auctions, mapping, commissions, reporting, invoicing, payments, blacklist.
    """,

    'description': """
        Real Estate Management System
    """,
    "author": "digitalvizta",
    "website" : "https://digitalvizta.com/",
    'price': '0.0',
    'currency': 'USD',
    'license': 'LGPL-3',
    'depends': ['base', 'mail', 'sale_management', 'website',
                'base_geolocalize', 'web', 'sale', 'board'],
    'data': [
        'security/user_groups.xml',
        'security/property_security.xml',
        'security/ir.model.access.csv',
        'data/ir_sequence_data.xml',
        'data/real_estate_management_data.xml',
        'data/ir_cron_data.xml',
        'views/property_property_views.xml',
        'views/property_facility_views.xml',
        'views/property_tag_views.xml',
        'views/property_search_pannel_views.xml',
        'views/property_templates.xml',
        'views/property_commision_views.xml',
        'views/property_sale_views.xml',
        'views/property_rental_views.xml',
        'views/res_partner_views.xml',
        'views/rental_bill_views.xml',
        'views/property_auction_views.xml',
        'views/sales_dashboard.xml',
        'reports/property_sale_report.xml',
        'reports/property_report.xml',
        'wizards/property_sale_report_views.xml',
    ],
    'assets': {
        'web.assets_frontend': [
            'dvz_real_estate_management/static/src/js/property_website.js',
            'dvz_real_estate_management/static/src/js/property_item.js',
        ],
        'web.assets_backend': [
            'dvz_real_estate_management/static/src/components/**/*.js',
            'dvz_real_estate_management/static/src/components/**/*.xml',
            'dvz_real_estate_management/static/src/components/**/*.scss',
        ],
    },
    'demo': [
        
    ],
    'images': ['static/description/banner.gif'],
    'installable': True,
    'application': True,
    'auto_install': False,
    'qweb': [
        
    ],
}
