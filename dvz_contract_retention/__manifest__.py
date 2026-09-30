{
    "name": "Retention Release & Bank Guarantees",
    "summary": "Release retention at handover and after the defects period, track bank guarantees with expiry reminders",
    "description": """
Paid add-on of the DigitalVizta Contracting Suite.

* Retention ledger per contract: held, released, balance
* Retention release documents (handover / end of defects period / other)
* Release invoice created automatically when retention was deducted on invoices
* Automatic release draft at handover (configurable %)
* Bank guarantees: bid, performance, advance, retention; given or received
* Expiry and defects-period reminders as scheduled activities
* Works on Odoo 19 Community and Enterprise
""",
    "version": "19.0.1.0.0",
    "category": "Services/Project",
    "author": "DigitalVizta",
    "website": "https://digitalvizta.net",
    "support": "info@digitalvizta.net",
    "license": "OPL-1",
    "price": 79.0,
    "currency": "USD",
    "depends": ["dvz_contract_ipc"],
    "data": [
        "security/dvz_contract_retention_security.xml",
        "security/ir.model.access.csv",
        "data/dvz_contract_retention_data.xml",
        "views/dvz_retention_release_views.xml",
        "views/dvz_bank_guarantee_views.xml",
        "views/dvz_contract_views.xml",
        "views/res_config_settings_views.xml",
        "views/dvz_contract_retention_menus.xml",
    ],
    "images": ["static/description/banner.png"],
    "installable": True,
}
