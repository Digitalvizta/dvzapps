{
    "name": "Variation Orders for Contractors",
    "summary": "Change orders with approval: add new BOQ items or adjust quantities and rates, update contract value",
    "description": """
Paid add-on of the DigitalVizta Contracting Suite.

* Variation orders (VO / change orders) per contract
* Add new BOQ items or adjust quantities and rates of existing ones
* Instruction, submission, approval, rejection workflow
* Approved variations update the BOQ and contract value in one click
* Time extension: extend the planned completion date
* Variation register PDF and analysis
* Works on Odoo 19 Community and Enterprise
""",
    "version": "19.0.1.0.0",
    "category": "Services/Project",
    "author": "DigitalVizta",
    "website": "https://digitalvizta.net",
    "support": "info@digitalvizta.net",
    "license": "OPL-1",
    "price": 69.0,
    "currency": "USD",
    "depends": ["dvz_contract"],
    "data": [
        "security/dvz_contract_variation_security.xml",
        "security/ir.model.access.csv",
        "views/dvz_contract_variation_views.xml",
        "views/dvz_contract_views.xml",
        "views/res_config_settings_views.xml",
        "report/dvz_contract_variation_report.xml",
        "views/dvz_contract_variation_menus.xml",
    ],
    "images": ["static/description/banner.png"],
    "installable": True,
}
