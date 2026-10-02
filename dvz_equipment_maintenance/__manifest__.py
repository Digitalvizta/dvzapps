{
    'name': 'Equipment Maintenance, Service Plans & Document Expiry (Istimara, Insurance, TPI)',
    'version': '19.0.1.0.0',
    'category': 'Services',
    'summary': 'Preventive service by hour meter, breakdown and repair log with cost and downtime, and expiry alerts '
               'for equipment documents: registration (Istimara), insurance, TPI / third-party inspection.',
    'description': """
Equipment Maintenance & Document Expiry
=======================================
Add-on for Equipment Rental (Heavy Equipment & Fleet):

* Service interval per machine in engine hours (e.g. every 250 h)
* Next service due, "due soon" and "overdue" status from the hour meter
* Service log: preventive, breakdown, repair and inspection with cost, vendor and downtime
* Machine goes to "In Maintenance" while a job is open and back in service when done
* Equipment documents: registration (Istimara), insurance, TPI certificate, MVPI (Fahas), operator card
* Daily expiry and service alerts as to-dos for the responsible person
* Blocks dispatch of a machine with an expired document
""",
    'author': 'DigitalVizta',
    'website': 'https://digitalvizta.net',
    'support': 'info@digitalvizta.net',
    'license': 'OPL-1',
    'price': 49.0,
    'currency': 'USD',
    'depends': ['dvz_equipment_rental'],
    'data': [
        'security/ir.model.access.csv',
        'security/maintenance_security.xml',
        'data/ir_cron_data.xml',
        'views/equipment_service_views.xml',
        'views/equipment_document_views.xml',
        'views/equipment_views.xml',
        'views/res_config_settings_views.xml',
    ],
    'post_init_hook': 'post_init_hook',
    'images': ['static/description/banner.png'],
    'installable': True,
    'application': False,
}
