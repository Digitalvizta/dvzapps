"""Demo data for the DigitalVizta Contracting Suite.

Install this module on a FRESH demo database (Saudi Arabia localisation recommended).
It configures Settings > Contracting and creates realistic documents in every state,
so a product demo can be recorded straight away.
"""
import logging
from datetime import timedelta

from dateutil.relativedelta import relativedelta

from odoo import fields

_logger = logging.getLogger(__name__)


def _ref(env, xmlid):
    return env.ref(xmlid, raise_if_not_found=False)


def _account(env, company, code, name, account_type):
    Account = env['account.account'].with_company(company)
    acc = Account.search([('code', '=', code), ('company_ids', 'in', company.id)], limit=1)
    if acc:
        return acc
    vals = {'code': code, 'name': name, 'account_type': account_type, 'company_ids': [(6, 0, company.ids)]}
    if account_type == 'asset_current':
        vals['reconcile'] = True
    return Account.create(vals)


def _dvz_setup_accounting(env, pending=None):
    """Load a chart of accounts if the company has none (Saudi chart by default)."""
    company = env.company
    if company.chart_template:
        return
    sa = _ref(env, 'base.sa')
    if not company.country_id and sa:
        company.country_id = sa
    if sa and company.country_id == sa:
        env['account.chart.template'].try_loading('sa', company, install_demo=False)
    elif pending:
        pending(env)
    else:
        env['account.chart.template'].try_loading('generic_coa', company, install_demo=False)


def _ensure_journals(env, company):
    Journal = env['account.journal'].with_company(company)

    def journal(jtype, name, code):
        j = Journal.search([('company_id', '=', company.id), ('type', '=', jtype)], limit=1)
        return j or Journal.create({'name': name, 'code': code, 'type': jtype, 'company_id': company.id})

    return journal('sale', 'Customer Invoices', 'INV'), journal('purchase', 'Vendor Bills', 'BILL')


def _dvz_post_init(env):
    """Entry point (post_init_hook).

    When Accounting is installed in the same run, Odoo loads the chart of accounts only after
    all modules are loaded. The demo needs accounts and journals, so in that case it is
    chained after the chart loading instead of running now.
    """
    pending = getattr(env.registry, '_auto_install_template', None)
    if pending or not env.company.chart_template:
        def _run(env2):
            _dvz_setup_accounting(env2, pending)
            _dvz_load_demo(env2)
        env.registry._auto_install_template = _run
    else:
        _dvz_load_demo(env)


def _tax(env, company, use):
    taxes = env['account.tax'].search([
        ('company_id', '=', company.id), ('type_tax_use', '=', use),
        ('amount_type', '=', 'percent'), ('amount', '=', 15.0)], limit=1)
    return taxes


def _try_post(move):
    try:
        with move.env.cr.savepoint():
            move.action_post()
    except Exception as e:  # e.g. e-invoicing not onboarded: keep the invoice in draft
        _logger.info('Demo: invoice %s left in draft (%s)', move.display_name, e)


def _set_progress(cert, quantities):
    """quantities: {item_no: qty_this_period}"""
    for line in cert.line_ids.filtered(lambda l: not l.display_type):
        if line.item_no in quantities:
            line.qty_current = quantities[line.item_no]


def _new_certificate(contract, date, quantities, consultant='Eng. Faisal Al-Harbi (Consultant)'):
    Cert = contract.env['dvz.contract.certificate']
    last = contract.certificate_ids.filtered(lambda c: c.state != 'cancel').sorted('date')[-1:]
    cert = Cert.create({
        'contract_id': contract.id,
        'date': date,
        'period_start': last.period_end and last.period_end + timedelta(days=1) or contract.date_start,
        'period_end': date,
        'consultant': consultant,
    })
    _set_progress(cert, quantities)
    return cert


def _dvz_load_demo(env):
    company = env.company
    today = fields.Date.context_today(env['res.users'])
    if company.name in ('My Company', 'YourCompany', 'My Company (San Francisco)'):
        company.write({'name': 'Al Bina Contracting Co. (Demo)', 'city': 'Riyadh',
                       'street': 'King Fahd Road, Al Olaya'})

    # ------------------------------------------------------------------ users / groups
    admin = _ref(env, 'base.user_admin')
    for xmlid in ('dvz_contract.group_dvz_contract_manager', 'dvz_contract.group_dvz_show_cost',
                  'analytic.group_analytic_accounting', 'purchase.group_purchase_manager'):
        group = _ref(env, xmlid)
        if group and admin:
            admin.write({'group_ids': [(4, group.id)]}) if 'group_ids' in admin._fields else \
                admin.write({'groups_id': [(4, group.id)]})
    if admin:
        # run the rest as the administrator (a contracting manager) so approvals pass
        env = env(user=admin.id, su=True)
        company = company.with_env(env)

    # ------------------------------------------------------------------ accounts & settings
    sale_journal, purchase_journal = _ensure_journals(env, company)
    retention_rec = _account(env, company, '121500', 'Retention Receivable', 'asset_current')
    advance_rec = _account(env, company, '221500', 'Advances Received from Clients', 'liability_current')
    deductions = _account(env, company, '411900', 'Back-charges and Penalties (Clients)', 'income')
    revenue = _account(env, company, '411100', 'Contract Revenue - Work Certified', 'income')
    sub_cost = _account(env, company, '511100', 'Subcontract Costs', 'expense_direct_cost')
    retention_pay = _account(env, company, '221600', 'Retention Payable to Subcontractors', 'liability_current')
    advance_paid = _account(env, company, '121600', 'Advances Paid to Subcontractors', 'asset_current')
    backcharges = _account(env, company, '511900', 'Back-charges to Subcontractors', 'expense_direct_cost')

    sale_tax = _tax(env, company, 'sale')
    purchase_tax = _tax(env, company, 'purchase')

    Product = env['product.product']
    work_product = Product.create({'name': 'Construction Works (Certified)', 'type': 'service',
                                   'sale_ok': True, 'purchase_ok': False})
    sub_product = Product.create({'name': 'Subcontract Works', 'type': 'service',
                                  'sale_ok': False, 'purchase_ok': True})

    company.write({
        'dvz_retention_percent': 10.0,
        'dvz_advance_percent': 10.0,
        'dvz_advance_recovery_percent': 10.0,
        'dvz_defects_months': 12,
        'dvz_sale_tax_ids': [(6, 0, sale_tax.ids)],
        'dvz_purchase_tax_ids': [(6, 0, purchase_tax.ids)],
        'dvz_lock_boq': True,
        'dvz_analytic_per_contract': True,
        'dvz_ipc_approval': True,
        'dvz_ipc_entry_mode': 'qty',
        'dvz_ipc_invoice_layout': 'summary',
        'dvz_retention_method': 'deduct',
        'dvz_ipc_journal_id': sale_journal.id,
        'dvz_ipc_product_id': work_product.id,
        'dvz_ipc_revenue_account_id': revenue.id,
        'dvz_retention_account_id': retention_rec.id,
        'dvz_advance_account_id': advance_rec.id,
        'dvz_deduction_account_id': deductions.id,
        'dvz_advance_tax': True,
        'dvz_recovery_tax': True,
        'dvz_allow_overrun': False,
        'dvz_ipc_auto_post': False,
        'dvz_ipc_bilingual': True,
        'dvz_variation_approval': True,
        'dvz_variation_auto_apply': True,
        'dvz_variation_allow_omission': True,
        'dvz_release_at_handover': True,
        'dvz_release_handover_percent': 50.0,
        'dvz_dlp_reminder_days': 30,
        'dvz_guarantee_reminder_days': 30,
        'dvz_guarantee_auto_expire': True,
        'dvz_sub_use_main_analytic': True,
        'dvz_sub_journal_id': purchase_journal.id,
        'dvz_sub_product_id': sub_product.id,
        'dvz_sub_cost_account_id': sub_cost.id,
        'dvz_sub_retention_account_id': retention_pay.id,
        'dvz_sub_advance_account_id': advance_paid.id,
        'dvz_sub_backcharge_account_id': backcharges.id,
    })

    # ------------------------------------------------------------------ partners
    sa = _ref(env, 'base.sa')
    Partner = env['res.partner']

    def partner(name, city, vat, is_sub=False):
        vals = {'name': name, 'is_company': True, 'city': city, 'country_id': sa.id if sa else False,
                'street': 'Demo Street', 'supplier_rank': 1 if is_sub else 0, 'customer_rank': 0 if is_sub else 1}
        try:
            with env.cr.savepoint():
                return Partner.create(dict(vals, vat=vat))
        except Exception:  # VAT validation (base_vat / e-invoicing) refused the demo number
            return Partner.create(vals)

    riyadh_dev = partner('Riyadh Urban Development Co. (Demo)', 'Riyadh', '300000000000003')
    gulf_re = partner('Gulf Real Estate Developers (Demo)', 'Jeddah', '300000000100003')
    eastern = partner('Eastern Industrial Services (Demo)', 'Dammam', '300000000200003')
    steel_sub = partner('Al Noor Steel Fixing Est. (Demo)', 'Riyadh', '300000000300003', True)
    mep_sub = partner('Delta MEP Services (Demo)', 'Riyadh', '300000000400003', True)
    bank = env['res.bank'].search([('name', 'ilike', 'Demo Bank')], limit=1) or \
        env['res.bank'].create({'name': 'Saudi National Bank (Demo)', 'bic': 'NCBKSAJE'})

    # ------------------------------------------------------------------ projects
    Project = env['project.project']
    p_villas = Project.create({'name': 'Al Narjis Villa Compound - Phase 2', 'partner_id': riyadh_dev.id})
    p_fitout = Project.create({'name': 'Jeddah Corniche Tower - Office Fit-out', 'partner_id': gulf_re.id})
    p_warehouse = Project.create({'name': 'Dammam 2nd Industrial City - Warehouse', 'partner_id': eastern.id})
    p_school = Project.create({'name': 'Al Malqa Private School - Extension', 'partner_id': riyadh_dev.id})

    uom = {k: _ref(env, 'uom.product_uom_%s' % v) for k, v in {
        'm3': 'cubic_meter', 'm2': 'square_meter', 'm': 'meter', 'ton': 'ton', 'nr': 'unit'}.items()}

    def boq(rows):
        lines, seq = [], 0
        for row in rows:
            seq += 10
            if isinstance(row, str):
                lines.append((0, 0, {'display_type': 'line_section', 'name': row, 'sequence': seq}))
                continue
            item, desc, unit, qty, rate, cost = row
            lines.append((0, 0, {'item_no': item, 'name': desc, 'uom_id': uom[unit].id if uom.get(unit) else False,
                                 'quantity': qty, 'price_unit': rate, 'cost_unit': cost, 'sequence': seq}))
        return lines

    Contract = env['dvz.contract']
    start = today - relativedelta(months=5, day=1)

    # ------------------------------------------------------------------ contract 1: villas (main demo)
    c1 = Contract.create({
        'title': 'Structural and Civil Works - 24 Villas',
        'partner_id': riyadh_dev.id, 'project_id': p_villas.id,
        'date_start': start, 'date_end': start + relativedelta(months=14),
        'retention_percent': 10.0, 'advance_percent': 10.0, 'advance_recovery_percent': 10.0,
        'scope': '<p>Excavation, foundations, reinforced concrete frame, block work and external works for 24 villas.</p>',
        'line_ids': boq([
            'A - Earthworks',
            ('A.01', 'Excavation for foundations in any soil, including disposal', 'm3', 4200, 28.0, 19.0),
            ('A.02', 'Backfilling with approved selected material, compacted in layers', 'm3', 2600, 22.0, 15.0),
            ('A.03', 'Anti-termite treatment below slabs and foundations', 'm2', 6800, 6.5, 4.0),
            'B - Concrete Works',
            ('B.01', 'Plain concrete blinding C15, 50 mm thick', 'm3', 340, 310.0, 240.0),
            ('B.02', 'Reinforced concrete C35 in foundations and ground beams', 'm3', 2150, 640.0, 505.0),
            ('B.03', 'Reinforced concrete C35 in columns, beams and slabs', 'm3', 3900, 720.0, 570.0),
            ('B.04', 'Reinforcement steel bars Grade 60, cut, bent and fixed', 'ton', 820, 3650.0, 3050.0),
            'C - Masonry',
            ('C.01', '200 mm hollow concrete block walls', 'm2', 14500, 78.0, 58.0),
            ('C.02', '100 mm solid block partition walls', 'm2', 5200, 64.0, 47.0),
            'D - External Works',
            ('D.01', 'Interlock paving 80 mm on sand bed', 'm2', 7600, 72.0, 52.0),
            ('D.02', 'Boundary wall 2.4 m high, complete', 'm', 1150, 540.0, 410.0),
        ]),
    })
    c1.action_confirm()
    adv = c1.action_create_advance_invoice()
    adv_move = env['account.move'].browse(adv['res_id'])
    _try_post(adv_move)

    guarantees = env['dvz.bank.guarantee']
    guarantees.create({'name': 'LG-PB-2026-0187', 'contract_id': c1.id, 'guarantee_type': 'performance',
                       'direction': 'given', 'partner_id': riyadh_dev.id, 'bank_id': bank.id,
                       'amount': c1.amount_untaxed * 0.05, 'commission_percent': 1.0,
                       'issue_date': start, 'expiry_date': start + relativedelta(months=26)})
    guarantees.create({'name': 'LG-AP-2026-0188', 'contract_id': c1.id, 'guarantee_type': 'advance',
                       'direction': 'given', 'partner_id': riyadh_dev.id, 'bank_id': bank.id,
                       'amount': c1.amount_untaxed * 0.10, 'commission_percent': 1.0,
                       'issue_date': start, 'expiry_date': today + timedelta(days=20)})

    # certificates: 3 approved & invoiced, 1 submitted (to approve live), 1 draft (to fill live)
    m = lambda n: start + relativedelta(months=n, day=25)
    cert_plan = [
        (m(1), {'A.01': 2500, 'A.03': 1500, 'B.01': 120}),
        (m(2), {'A.01': 1500, 'A.02': 900, 'A.03': 2800, 'B.01': 160, 'B.02': 900, 'B.04': 110}),
        (m(3), {'A.01': 200, 'A.02': 1000, 'A.03': 2500, 'B.01': 60, 'B.02': 1000, 'B.03': 600, 'B.04': 230}),
    ]
    for date, qty in cert_plan:
        cert = _new_certificate(c1, date, qty)
        cert.action_submit()
        cert.action_approve()
        cert.action_create_invoice()
        _try_post(cert.invoice_id)
    c4 = _new_certificate(c1, m(4), {'A.02': 500, 'B.02': 200, 'B.03': 900, 'B.04': 180, 'C.01': 2400})
    c4.deduction_ids = [(0, 0, {'name': 'Site cleaning back-charge', 'deduction_type': 'backcharge',
                                'reason': 'Debris left at gate 2, cleaned by client', 'amount': 8500.0})]
    c4.action_submit()

    # variations: one applied, one submitted (approve it live)
    Var = env['dvz.contract.variation']
    vo1 = Var.create({
        'contract_id': c1.id, 'title': 'Additional guard house and gate canopy',
        'reason': 'client_instruction', 'instruction_ref': 'SI-014', 'time_extension_days': 21,
        'date': m(3) - timedelta(days=10),
        'line_ids': [
            (0, 0, {'change_type': 'new', 'item_no': 'V1.01', 'name': 'Guard house 4 x 5 m, RC frame and block work, complete',
                    'uom_id': uom['nr'].id, 'quantity': 2, 'price_unit': 68500.0, 'cost_unit': 52000.0}),
            (0, 0, {'change_type': 'change', 'contract_line_id': c1.line_ids.filtered(lambda l: l.item_no == 'D.02').id,
                    'item_no': 'D.02', 'name': 'Boundary wall 2.4 m high, complete', 'uom_id': uom['m'].id,
                    'quantity': 120, 'price_unit': 540.0, 'cost_unit': 410.0}),
        ],
    })
    vo1.action_submit()
    vo1.action_approve()
    Var.create({
        'contract_id': c1.id, 'title': 'Upgrade of external paving to granite at main entrance',
        'reason': 'design_change', 'instruction_ref': 'DWG-EX-205 Rev B', 'time_extension_days': 7,
        'line_ids': [
            (0, 0, {'change_type': 'new', 'item_no': 'V2.01', 'name': 'Granite paving 30 mm, flamed finish, on screed',
                    'uom_id': uom['m2'].id, 'quantity': 420, 'price_unit': 245.0, 'cost_unit': 180.0}),
            (0, 0, {'change_type': 'change', 'contract_line_id': c1.line_ids.filtered(lambda l: l.item_no == 'D.01').id,
                    'item_no': 'D.01', 'name': 'Interlock paving 80 mm (omitted at entrance)', 'uom_id': uom['m2'].id,
                    'quantity': -420, 'price_unit': 72.0, 'cost_unit': 52.0}),
        ],
    }).action_submit()

    # subcontract under contract 1
    sub = Contract.with_context(default_contract_type='subcontract').create({
        'contract_type': 'subcontract', 'parent_contract_id': c1.id,
        'title': 'Steel fixing - labour and tools', 'partner_id': steel_sub.id, 'project_id': p_villas.id,
        'date_start': start + relativedelta(months=1), 'date_end': c1.date_end,
        'retention_percent': 5.0, 'advance_percent': 0.0, 'advance_recovery_percent': 0.0,
        'tax_ids': [(6, 0, purchase_tax.ids)],
        'line_ids': boq([('S.01', 'Cut, bend and fix reinforcement, labour only', 'ton', 820, 650.0, 0.0)]),
    })
    sub.action_confirm()
    s1 = _new_certificate(sub, m(3), {'S.01': 340}, consultant='')
    s1.action_submit()
    s1.action_approve()
    s1.action_create_invoice()
    guarantees.create({'name': 'LG-REC-0912', 'contract_id': sub.id, 'guarantee_type': 'performance',
                       'direction': 'received', 'partner_id': steel_sub.id, 'bank_id': bank.id,
                       'amount': sub.amount_untaxed * 0.05, 'issue_date': start,
                       'expiry_date': today - timedelta(days=5)})
    Contract.with_context(default_contract_type='subcontract').create({
        'contract_type': 'subcontract', 'parent_contract_id': c1.id,
        'title': 'Plumbing and drainage - 24 villas', 'partner_id': mep_sub.id, 'project_id': p_villas.id,
        'retention_percent': 10.0, 'tax_ids': [(6, 0, purchase_tax.ids)],
        'line_ids': boq([('M.01', 'Internal water supply and drainage per villa', 'nr', 24, 38500.0, 0.0)]),
    })

    # ------------------------------------------------------------------ contract 2: fit-out (in progress)
    c2 = Contract.create({
        'title': 'Office Fit-out Floors 12 to 15',
        'partner_id': gulf_re.id, 'project_id': p_fitout.id,
        'date_start': start + relativedelta(months=2), 'date_end': start + relativedelta(months=9),
        'retention_percent': 10.0, 'advance_percent': 0.0, 'advance_recovery_percent': 0.0,
        'line_ids': boq([
            'Partitions and Ceilings',
            ('F.01', 'Gypsum board partitions, double layer, acoustic insulation', 'm2', 3800, 165.0, 120.0),
            ('F.02', 'Suspended mineral fibre ceiling 600 x 600', 'm2', 6100, 95.0, 68.0),
            'Floor Finishes',
            ('F.03', 'Raised access floor 600 mm panels', 'm2', 5200, 210.0, 160.0),
            ('F.04', 'Carpet tiles, heavy contract grade', 'm2', 4300, 88.0, 61.0),
            'Joinery',
            ('F.05', 'Reception counter, Corian top, complete', 'nr', 4, 42000.0, 31000.0),
        ]),
    })
    c2.action_confirm()
    cert = _new_certificate(c2, m(4), {'F.01': 1400, 'F.02': 900})
    cert.action_submit()
    cert.action_approve()
    cert.action_create_invoice()
    _try_post(cert.invoice_id)

    # ------------------------------------------------------------------ contract 3: warehouse (draft, to confirm live)
    Contract.create({
        'title': 'Pre-engineered Steel Warehouse 6,000 m2',
        'partner_id': eastern.id, 'project_id': p_warehouse.id,
        'date_start': today + timedelta(days=14), 'date_end': today + relativedelta(months=8),
        'line_ids': boq([
            'Civil',
            ('W.01', 'Isolated footings and tie beams, RC C35', 'm3', 980, 690.0, 540.0),
            ('W.02', 'Ground slab 200 mm, power-floated, with joints', 'm2', 6000, 145.0, 108.0),
            'Steel Structure',
            ('W.03', 'Pre-engineered steel building, supply and erect', 'ton', 310, 7800.0, 6400.0),
            ('W.04', 'Sandwich panel cladding and roofing 50 mm', 'm2', 9800, 115.0, 86.0),
        ]),
    })

    # ------------------------------------------------------------------ contract 4: school (handed over, retention)
    old_start = today - relativedelta(months=16, day=1)
    c5 = Contract.create({
        'title': 'Classroom Block Extension',
        'partner_id': riyadh_dev.id, 'project_id': p_school.id,
        'date_start': old_start, 'date_end': old_start + relativedelta(months=9),
        'retention_percent': 10.0, 'advance_percent': 0.0, 'advance_recovery_percent': 0.0,
        'defects_months': 12,
        'line_ids': boq([
            ('K.01', 'Classroom block, structure and finishes, complete', 'm2', 1800, 2350.0, 1820.0),
            ('K.02', 'External works and landscaping', 'm2', 1200, 180.0, 130.0),
        ]),
    })
    c5.action_confirm()
    for n, qty in ((2, {'K.01': 600}), (5, {'K.01': 900, 'K.02': 400}), (8, {'K.01': 300, 'K.02': 800})):
        cert = _new_certificate(c5, old_start + relativedelta(months=n, day=25), qty)
        cert.action_submit()
        cert.action_approve()
        cert.action_create_invoice()
        _try_post(cert.invoice_id)
    c5.write({'handover_date': old_start + relativedelta(months=10)})
    c5.action_handover()
    rel = c5.release_ids.filtered(lambda r: r.release_type == 'handover')[:1]
    if rel:
        rel.date = c5.handover_date
        rel.action_release()
        if rel.invoice_id:
            _try_post(rel.invoice_id)
    env['dvz.bank.guarantee'].create({
        'name': 'LG-BID-2026-0044', 'guarantee_type': 'bid', 'direction': 'given', 'partner_id': eastern.id,
        'bank_id': bank.id, 'amount': 150000.0, 'issue_date': today - relativedelta(months=2),
        'expiry_date': today + relativedelta(months=1)})
    _dvz_demo_procurement(env, company, c1, c2, uom, today)
    _dvz_demo_portal(env, c1, c2)
    env['dvz.contract']._cron_dlp_reminders()
    env['dvz.bank.guarantee']._cron_guarantee_reminders()
    env['dvz.cashflow.line']._rebuild(company)
    _logger.info('DigitalVizta Contracting demo data loaded.')


# ---------------------------------------------------------------------- procurement
def _dvz_demo_procurement(env, company, c1, c2, uom, today):
    sa = _ref(env, 'base.sa')
    Partner = env['res.partner']

    def vendor(name, city):
        return Partner.create({'name': name, 'is_company': True, 'city': city, 'street': 'Industrial Area',
                               'country_id': sa.id if sa else False, 'supplier_rank': 1})

    concrete_v = vendor('Najd Ready Mix Concrete (Demo)', 'Riyadh')
    steel_v = vendor('Arabian Rebar Trading (Demo)', 'Dammam')
    block_v = vendor('Riyadh Block Factory (Demo)', 'Riyadh')
    fitout_v = vendor('Gulf Interiors Supply (Demo)', 'Jeddah')
    purchase_tax = company.dvz_purchase_tax_ids[:1]

    def product(name, unit, cost, seller, price):
        vals = {
            'name': name, 'type': 'consu', 'purchase_ok': True, 'sale_ok': False,
            'standard_price': cost, 'purchase_method': 'purchase',
            'supplier_taxes_id': [(6, 0, purchase_tax.ids)],
            'seller_ids': [(0, 0, {'partner_id': seller.id, 'price': price, 'min_qty': 0.0})],
        }
        if uom.get(unit):
            vals['uom_id'] = uom[unit].id
        return env['product.product'].create(vals)

    p_c35 = product('Ready-mix concrete C35 (SRC)', 'm3', 300.0, concrete_v, 305.0)
    p_c15 = product('Ready-mix concrete C15 blinding', 'm3', 215.0, concrete_v, 250.0)
    p_rebar = product('Reinforcement steel bars Grade 60', 'ton', 2650.0, steel_v, 2650.0)
    p_block = product('Hollow concrete block 200 mm', 'nr', 3.2, block_v, 3.2)
    p_gypsum = product('Gypsum board 12.5 mm, moisture resistant', 'm2', 28.0, fitout_v, 28.0)

    def boq(contract, item):
        return contract.line_ids.filtered(lambda l: l.item_no == item)[:1]

    MR = env['dvz.material.request']

    def request(contract, lines, required, location, stop='ordered', bill=False):
        mr = MR.create({
            'contract_id': contract.id,
            'date': today - timedelta(days=30) if stop == 'ordered' else today,
            'date_required': required,
            'location': location,
            'line_ids': [(0, 0, {
                'contract_line_id': boq(contract, item).id,
                'product_id': prod.id,
                'quantity': qty,
                'vendor_id': prod.seller_ids[:1].partner_id.id,
                'price_unit': prod.seller_ids[:1].price,
            }) for item, prod, qty in lines],
        })
        if stop == 'draft':
            return mr
        mr.action_submit()
        if stop == 'submitted':
            return mr
        mr.action_approve()
        mr.action_create_rfq()
        for order in mr.purchase_ids:
            order.button_confirm()
            if bill:
                order.action_create_invoice()
                for move in order.invoice_ids.filtered(lambda m: m.state == 'draft'):
                    move.invoice_date = today - timedelta(days=10)
                    _try_post(move)
        return mr

    # 1. rebar: ordered and billed (actual cost)
    request(c1, [('B.04', p_rebar, 220)], today - timedelta(days=20), 'Villas 1-12, ground beams', bill=True)
    # 2. concrete: ordered, not billed yet (committed cost)
    request(c1, [('B.02', p_c35, 900)], today + timedelta(days=5), 'Villas 13-24, foundations')
    # 3. blinding: price went up, takes the BOQ item over budget (red line in Budget vs Actual)
    request(c1, [('B.01', p_c15, 340)], today + timedelta(days=3), 'All villas, blinding')
    # 4. blocks: waiting for approval (approve it live)
    request(c1, [('C.01', p_block, 30000)], today + timedelta(days=14), 'Villas 1-6, ground floor walls',
            stop='submitted')
    # 5. fit-out gypsum board: draft request
    request(c2, [('F.01', p_gypsum, 3800)], today + timedelta(days=21), 'Floor 13, partitions', stop='draft')


# ---------------------------------------------------------------------- portal
def _dvz_demo_portal(env, c1, c2):
    Partner = env['res.partner']
    firm = Partner.create({'name': 'Al Rowad Engineering Consultants (Demo)', 'is_company': True, 'city': 'Riyadh',
                           'country_id': (_ref(env, 'base.sa') or Partner).id})
    consultant = Partner.create({'name': 'Eng. Faisal Al-Harbi', 'parent_id': firm.id,
                                 'email': 'consultant@demo.com', 'function': 'Resident Engineer'})
    portal_group = _ref(env, 'base.group_portal')
    Users = env['res.users'].with_context(no_reset_password=True, mail_create_nosubscribe=True)
    login = 'consultant@demo.com'
    if portal_group and not Users.search([('login', '=', login)], limit=1):
        groups_field = 'group_ids' if 'group_ids' in Users._fields else 'groups_id'
        try:
            with env.cr.savepoint():
                Users.create({'name': consultant.name, 'login': login, 'password': 'consultant',
                              'partner_id': consultant.id, groups_field: [(6, 0, [portal_group.id])]})
        except Exception as e:
            _logger.info('Demo: portal user not created (%s)', e)
    (c1 | c2).write({'consultant_ids': [(4, consultant.id)]})
    certs = (c1 | c2).certificate_ids.filtered(lambda c: c.state == 'submitted')
    variations = (c1 | c2).variation_ids.filtered(lambda v: v.state == 'submitted')
    certs._dvz_portal_notify()
    variations._dvz_portal_notify()
