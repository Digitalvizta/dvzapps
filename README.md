# DigitalVizta Contracting Suite for Odoo 19

Six modules for construction contractors. They run on Odoo 19 Community and Enterprise, and every module name starts with `dvz_`.

| Technical name | App name (manifest) | License | Price (USD) | Depends on |
|---|---|---|---|---|
| dvz_contract | Contracts & BOQ for Contractors | LGPL-3 | Free | account, project, analytic, uom, mail |
| dvz_contract_ipc | Progress Billing (IPC) for Contractors | OPL-1 | 149 | dvz_contract |
| dvz_contract_retention | Retention Release & Bank Guarantees | OPL-1 | 79 | dvz_contract_ipc |
| dvz_contract_variation | Variation Orders for Contractors | OPL-1 | 69 | dvz_contract |
| dvz_contract_subcontract | Subcontractor Management & Certificates | OPL-1 | 99 | dvz_contract_ipc |
| dvz_contracting_suite | Contracting Suite for Construction Companies | OPL-1 | (no own price) | all five |

On the Odoo Apps Store, a buyer pays for the module plus any paid modules it depends on. For example:

- Retention costs 79 + 149 = 228.
- The suite costs the sum of all paid modules, which is 396.

You can change any price in `__manifest__.py`.

## Install (test server first)

1. Copy all six folders into your custom addons path (for example `/opt/odoo/custom-addons`).
2. Restart Odoo with that path in `addons_path`.
3. Go to Apps and click Update Apps List.
4. Install **Contracts & BOQ** first, then the paid modules you need, or install **Contracting Suite** to get everything.
5. From the command line, you can run the tests on a test database:
   `odoo-bin -d testdb -i dvz_contracting_suite --test-enable --stop-after-init`

**Important:** These modules were written for Odoo 19 and passed static checks: Python compile, XML parsing, manifest files, access rules and view fields. They were not installed on a live Odoo 19 server. Install on a test copy first, run the tests, and fix any error before going to production or publishing.

## Configuration (Settings > Contracting)

All settings are per company.

### Contract defaults (free)

- Retention %
- Advance %
- Advance recovery %
- Defects liability period (months)
- Default sale and purchase taxes
- Lock the BOQ after confirmation
- Show estimated cost on the BOQ (a user group)
- Create one analytic account per contract, and choose the analytic plan

### Payment certificates (IPC)

- Workflow:
  - Approval step on or off.
  - Progress entry by quantity or by cumulative %.
  - Invoice layout: one summary line, or one line per BOQ item.
  - Allow quantities above the BOQ.
  - Auto-post invoices.
  - Bilingual PDF.
- Retention method:
  - **Deduct on invoice**: a negative, tax-free line posted to the retention receivable account.
  - **Track only**: the invoice is for the full amount and retention is tracked on the certificate.
  - For ZATCA or other e-invoicing that rejects negative lines, use **Track only**.
- Accounting:
  - Journal
  - Product
  - Revenue account
  - Retention, advance and other-deduction accounts
  - Whether tax applies to the advance invoice and to the advance recovery

### Retention & guarantees

- Prepare a release draft at handover, and the % to release
- Reminder days before the defects period ends
- Reminder days before a guarantee expires
- Expire guarantees automatically (a daily scheduled job does this)

### Variations

- Approval required
- Apply to the BOQ automatically when approved
- Allow omissions (negative variations)

### Subcontractors

- Use the main contract's analytic account
- Vendor bills journal, product and cost account
- Retention payable, advances paid and back-charges accounts

## Suggested accounts

Create these in your chart of accounts before you start billing:

| Purpose | Type |
|---|---|
| Contract revenue | Income |
| Retention receivable | Current assets |
| Advances received from clients | Current liabilities |
| Other deductions / back-charges | Income or cost recovery |
| Subcontract costs | Expenses (direct costs) |
| Retention payable to subcontractors | Current liabilities |
| Advances paid to subcontractors | Current assets |

## Daily flow

1. Create the contract with its BOQ (you can import it from Excel), then confirm it.
2. If there is an advance payment, create the advance invoice.
3. Each month, create a new payment certificate, enter progress, then submit, approve and create the invoice.
4. For changes, create a variation, approve it, and it is applied to the BOQ.
5. For subcontractors, create a subcontract from the main contract. Their certificates become vendor bills.
6. At handover, a retention release draft is prepared. The balance is released when the defects period ends.

## Extending (developer hooks)

- `dvz.contract._on_handover()`: called after handover.
- `dvz.contract._check_can_cancel()`: blocks cancellation.
- `dvz.contract._get_dvz_accounts()`: returns the journal, product and accounts. Subcontracts override it for the vendor side.
- `dvz.contract.ipc._prepare_invoice_lines(acc)`, `_prepare_invoice(acc)`, `_after_invoice_created(move)`: customize invoicing.


## Support

DigitalVizta | info@digitalvizta.net | WhatsApp +92 304 6117529 | https://digitalvizta.net | https://www.linkedin.com/company/digitalvizta-tech

---

# DigitalVizta Manpower Supply Suite for Odoo 19

Six modules for Saudi manpower supply / labor outsourcing companies (Ajeer secondment). They run on Odoo 19 Community and Enterprise, and every module name starts with `dvz_manpower_`.

| Technical name | App name (manifest) | License | Price (USD) | Depends on |
|---|---|---|---|---|
| dvz_manpower_supply | Manpower Supply Contracts (KSA) | LGPL-3 | Free | hr, mail |
| dvz_manpower_documents | Worker Documents & Ajeer Expiry Alerts (KSA) | OPL-1 | 49 | dvz_manpower_supply |
| dvz_manpower_timesheet | Manpower Timesheets & Client Portal Approval (KSA) | OPL-1 | 79 | dvz_manpower_supply, portal |
| dvz_manpower_billing | Manpower Billing: Invoices from Timesheets (KSA, ZATCA) | OPL-1 | 79 | dvz_manpower_timesheet, account |
| dvz_manpower_profitability | Manpower Profitability: Profit per Worker & Contract (KSA) | OPL-1 | 49 | dvz_manpower_billing |
| dvz_manpower_suite | Manpower Supply Suite for Saudi Manpower Companies | OPL-1 | (no own price) | all five |

What buyers pay on the Odoo Apps Store (module + paid dependencies):

- Billing costs 79 + 79 = 158.
- Profitability costs 49 + 79 + 79 = 207.
- The suite costs the sum of all paid modules, which is 256.

## Install (test server first)

1. Copy the `dvz_manpower_*` folders into your custom addons path.
2. Restart Odoo, go to Apps and click Update Apps List.
3. Install **Manpower Supply Contracts** first, then the paid modules you need, or install **Manpower Supply Suite** to get everything.

Quick test: create a supply contract, add a rate line and activate it, assign a worker, add an Iqama that expires soon, create this month's timesheet ("Fill from Assignments"), send it to the client, approve it from "Client Preview", create the invoice, then enter worker costs and open Reporting > Profitability.

Notes:

- Set 15% VAT on the "Manpower Supply Service" and "Manpower Overtime" products if the chart of accounts was installed after the billing module.
- Users who create invoices need Invoicing rights.

**Important:** These modules were written for Odoo 19 and passed static checks (Python compile, XML parsing, Odoo view schemas, view fields and buttons, XML references, access rules) and a code review against the Odoo 19 source. They were not installed on a live Odoo 19 server. Install on a test copy first and fix any error before going to production or publishing.
