{
    "name": "Progress Billing (IPC) for Contractors",
    "summary": "Interim payment certificates from the BOQ: cumulative progress, retention, advance recovery, invoices",
    "description": """
Paid add-on of the DigitalVizta Contracting Suite.

* Interim payment certificates (IPC) built from the contract BOQ
* Enter progress by quantity or by cumulative percentage (configurable)
* Previous / current / cumulative quantities and amounts, overrun control
* Retention: deducted on the invoice or tracked only (configurable, ZATCA friendly)
* Advance payment invoice and automatic advance recovery per certificate
* Other deductions (back-charges, penalties) with their own account
* Optional approval step, auto-post, summary or detailed invoices
* Bilingual (English / Arabic) payment certificate PDF
* Works on Odoo 19 Community and Enterprise
""",
    "version": "19.0.1.0.0",
    "category": "Services/Project",
    "author": "DigitalVizta",
    "website": "https://digitalvizta.net",
    "support": "info@digitalvizta.net",
    "license": "OPL-1",
    "price": 149.0,
    "currency": "USD",
    "depends": ["dvz_contract"],
    "data": [
        "security/dvz_contract_ipc_security.xml",
        "security/ir.model.access.csv",
        "data/dvz_contract_ipc_data.xml",
        "views/dvz_contract_ipc_views.xml",
        "views/dvz_contract_views.xml",
        "views/res_config_settings_views.xml",
        "report/dvz_contract_ipc_report.xml",
        "report/dvz_contract_ipc_report_templates.xml",
        "views/dvz_contract_ipc_menus.xml",
    ],
    "images": ["static/description/banner.png"],
    "installable": True,
}
