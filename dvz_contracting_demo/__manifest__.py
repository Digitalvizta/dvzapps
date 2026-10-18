{
    'name': 'Contracting Suite - Demo Data (Saudi contractor)',
    'summary': 'Loads a realistic Saudi construction demo: contracts, BOQ, certificates, variations, subcontracts, guarantees.',
    'description': 'Install on a fresh demo database only. Creates demo partners, projects, accounts and documents '
                   'for recording product demos of the DigitalVizta Contracting Suite.',
    'version': '19.0.1.3.0',
    'category': 'Services/Contracting',
    'author': 'DigitalVizta',
    'website': 'https://digitalvizta.net/construction-erp/?utm_source=odoo_apps&utm_medium=app_store&utm_campaign=dvz_contracting_demo',
    'license': 'OPL-1',
    'depends': ['dvz_contracting_suite', 'l10n_sa'],
    'data': [],
    'post_init_hook': '_dvz_post_init',
    'installable': True,
}
