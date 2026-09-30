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

## Publish on the Odoo Apps Store

1. Create a Git repository, for example `github.com/Digitalvizta/odoo-contracting`, with a branch named `19.0`. Put the six module folders at the root of the repository.
2. Sign in at apps.odoo.com, go to **Upload your apps**, and add the repository URL with `#19.0`, for example `https://github.com/<you>/odoo-contracting.git#19.0`. For a private repository, give read access to the `online-odoo` user.
3. The store reads the following from each module:
   - The listing text from `static/description/index.html`.
   - The main image from `images` in the manifest (`static/description/banner.png`).
   - The icon from `static/description/icon.png`.
   - The price and license from the manifest.
4. Paid modules must stay OPL-1. The free core stays LGPL-3.
5. After the first scan, check each app page. Push again to update it; the store rescans the repository.

The screenshots in `static/description` are high-fidelity mock-ups of the module screens. Once the modules run on your test server, you can replace them with real screenshots under the same file names.

## Support

DigitalVizta | info@digitalvizta.net | WhatsApp +92 304 6117529 | https://digitalvizta.net | https://www.linkedin.com/company/digitalvizta-tech
