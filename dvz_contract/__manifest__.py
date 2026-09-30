{
    "name": "Contracts & BOQ for Contractors",
    "summary": "Construction contracts, bill of quantities (BOQ), contract value and cost control dashboard",
    "description": """
Free core of the DigitalVizta Contracting Suite.

* Client contracts with commercial terms (retention, advance payment, defects liability period)
* Bill of quantities with sections, notes, units, rates and estimated cost
* Contract value, cost budget and planned margin
* Cost control: budget vs committed (purchase) vs actual (analytic accounting)
* Automatic analytic account per contract
* Contract summary PDF
* Everything configurable in Settings > Contracting
""",
    "version": "19.0.1.0.0",
    "category": "Services/Project",
    "author": "DigitalVizta",
    "website": "https://digitalvizta.net",
    "support": "info@digitalvizta.net",
    "license": "LGPL-3",
    "depends": ["account", "project", "analytic", "uom", "mail"],
    "data": [
        "security/dvz_contract_security.xml",
        "security/ir.model.access.csv",
        "data/ir_sequence_data.xml",
        "views/dvz_contract_views.xml",
        "views/dvz_contract_line_views.xml",
        "views/res_config_settings_views.xml",
        "report/dvz_contract_report.xml",
        "report/dvz_contract_report_templates.xml",
        "views/dvz_contract_menus.xml",
    ],
    "images": ["static/description/banner.png"],
    "application": True,
    "installable": True,
}
