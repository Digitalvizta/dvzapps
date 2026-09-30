{
    "name": "Subcontractor Management & Certificates",
    "summary": "Subcontracts with BOQ, subcontractor payment certificates, vendor bills with retention and advance recovery",
    "description": """
Paid add-on of the DigitalVizta Contracting Suite.

* Subcontracts linked to the main client contract and its analytic account
* Subcontract BOQ, retention, advance and defects period
* Subcontractor payment certificates (same engine as client IPCs)
* Vendor bills created automatically with retention payable and advance recovery
* Separate vendor-side journal and accounts, all configurable
* Main contract shows committed subcontract value
* Works on Odoo 19 Community and Enterprise
""",
    "version": "19.0.1.0.0",
    "category": "Services/Project",
    "author": "DigitalVizta",
    "website": "https://digitalvizta.net",
    "support": "info@digitalvizta.net",
    "license": "OPL-1",
    "price": 99.0,
    "currency": "USD",
    "depends": ["dvz_contract_ipc"],
    "data": [
        "views/dvz_contract_views.xml",
        "views/dvz_contract_ipc_views.xml",
        "views/res_config_settings_views.xml",
        "views/dvz_contract_subcontract_menus.xml",
    ],
    "images": ["static/description/banner.png"],
    "installable": True,
}
