{
    "name": "Contracting Suite for Construction Companies",
    "summary": "All-in-one: contracts & BOQ, progress billing (IPC), retention & guarantees, variations, subcontractors",
    "description": """
Bundle of the DigitalVizta Contracting Suite. Installs:

* Contracts & BOQ for Contractors (free core)
* Progress Billing (IPC) for Contractors
* Retention Release & Bank Guarantees
* Variation Orders for Contractors
* Subcontractor Management & Certificates

Works on Odoo 19 Community and Enterprise.
""",
    "version": "19.0.1.0.0",
    "category": "Services/Project",
    "author": "DigitalVizta",
    "website": "https://digitalvizta.net",
    "support": "info@digitalvizta.net",
    "license": "OPL-1",
    "depends": [
        "dvz_contract",
        "dvz_contract_ipc",
        "dvz_contract_retention",
        "dvz_contract_variation",
        "dvz_contract_subcontract",
    ],
    "data": [],
    "images": ["static/description/banner.png"],
    "application": True,
    "installable": True,
}
