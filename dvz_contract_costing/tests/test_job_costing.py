from odoo import Command, fields
from odoo.tests import TransactionCase, tagged


@tagged('post_install', '-at_install')
class TestJobCosting(TransactionCase):

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.company = cls.env.company
        cls.company.dvz_analytic_per_contract = True
        cls.client = cls.env['res.partner'].create({'name': 'Riyadh Developer'})
        cls.categ_mat = cls.env['product.category'].create({'name': 'Building materials', 'dvz_cost_type': 'material'})
        cls.cement = cls.env['product.product'].create({
            'name': 'Cement bag', 'type': 'consu', 'categ_id': cls.categ_mat.id, 'standard_price': 20.0})
        cls.crane = cls.env['product.product'].create({
            'name': 'Mobile crane (hour)', 'type': 'service', 'dvz_cost_type': 'equipment', 'standard_price': 300.0})
        cls.rent = cls.env['product.product'].create({
            'name': 'Site office rent', 'type': 'service', 'dvz_cost_type': 'site_overhead'})
        cls.contract = cls.env['dvz.contract'].create({
            'title': 'Villa compound',
            'partner_id': cls.client.id,
            'costing_method': 'auto',
            'ho_overhead_percent': 5.0,
            'line_ids': [
                Command.create({'item_no': '1.1', 'name': 'Concrete works', 'quantity': 100, 'price_unit': 200.0,
                                'cost_material_unit': 80.0, 'cost_labour_unit': 40.0, 'cost_equipment_unit': 20.0,
                                'labour_hours_unit': 2.0}),
                Command.create({'item_no': '1.2', 'name': 'Block work', 'quantity': 50, 'price_unit': 100.0,
                                'cost_unit': 70.0}),
            ],
        })
        cls.contract.action_confirm()
        cls.concrete, cls.blocks = cls.contract.line_ids
        cls.employee = cls.env['hr.employee'].create({'name': 'Site foreman', 'hourly_cost': 25.0})

    def _cost(self, amount, **vals):
        column = self.contract._analytic_column()
        return self.env['account.analytic.line'].create(dict({
            'name': 'cost', 'amount': -amount, 'date': fields.Date.today(),
            column: self.contract.analytic_account_id.id,
        }, **vals))

    def _certify(self, qty_by_line):
        self.contract.action_new_certificate()
        cert = self.contract.certificate_ids.filtered(lambda c: c.state == 'draft')
        for line in cert.line_ids:
            if line.contract_line_id in qty_by_line:
                line.qty_current = qty_by_line[line.contract_line_id]
        cert.action_submit()
        if cert.state == 'submitted':
            cert.action_approve()
        return cert

    # ------------------------------------------------------------------
    def test_01_budget_split_sets_unit_cost(self):
        self.assertEqual(self.concrete.cost_unit, 140.0, 'Unit cost = material + labour + equipment')
        self.assertEqual(self.concrete.budget_material, 8000.0)
        self.assertEqual(self.concrete.budget_labour, 4000.0)
        self.assertEqual(self.concrete.budget_hours, 200.0)
        self.assertEqual(self.blocks.budget_other, 3500.0, 'Not split: whole budget is "other"')
        self.concrete.cost_overhead_unit = 10.0
        self.assertEqual(self.concrete.cost_unit, 150.0, 'Changing the split updates the unit cost')

    def test_02_classification(self):
        mat = self._cost(1000, product_id=self.cement.id)
        crane = self._cost(600, product_id=self.crane.id)
        rent = self._cost(500, product_id=self.rent.id)
        other = self._cost(100)
        self.assertEqual(mat.dvz_contract_id, self.contract)
        self.assertEqual(mat.dvz_cost_type, 'material')
        self.assertEqual(crane.dvz_cost_type, 'equipment')
        self.assertEqual(rent.dvz_cost_type, 'site_overhead')
        self.assertEqual(other.dvz_cost_type, 'other')
        # an account marked as labour classifies cost lines without product
        account = self.env['account.account'].create({
            'name': 'Site wages', 'code': '510099', 'account_type': 'expense', 'dvz_cost_type': 'labour'})
        wages = self._cost(300, general_account_id=account.id)
        self.assertEqual(wages.dvz_cost_type, 'labour')
        # set by hand: kept, even when the line changes later
        other.dvz_cost_type = 'subcontract'
        other.name = 'renamed'
        other.amount = -150
        self.assertEqual(other.dvz_cost_type, 'subcontract')
        self.assertTrue(other.dvz_cost_type_manual)

    def test_03_timesheet_is_labour_on_boq_item(self):
        project = self.env['project.project'].create({
            'name': 'Villa project', 'account_id': self.contract.analytic_account_id.id})
        task = project.task_ids.create({'name': 'Pour slab', 'project_id': project.id,
                                        'dvz_contract_line_id': self.concrete.id})
        sheet = self.env['account.analytic.line'].create({
            'name': 'Pouring', 'project_id': project.id, 'task_id': task.id, 'employee_id': self.employee.id,
            'unit_amount': 8.0,
        })
        self.assertEqual(sheet.dvz_contract_id, self.contract)
        self.assertEqual(sheet.dvz_cost_type, 'labour')
        self.assertEqual(sheet.dvz_contract_line_id, self.concrete)
        self.assertEqual(self.concrete.jc_actual_hours, 8.0)
        self.assertEqual(self.concrete.jc_actual, 200.0)

    def test_04_cost_to_complete_methods(self):
        self._cost(5000, product_id=self.cement.id, dvz_contract_line_id=self.concrete.id)
        self._certify({self.concrete: 50})        # half of the concrete is done
        self.contract.invalidate_recordset()
        line = self.concrete
        self.assertAlmostEqual(line.jc_progress, 50.0)
        # auto: remaining work at budget rates = 14000 * 50%
        self.assertAlmostEqual(line.jc_etc, 7000.0)
        self.assertAlmostEqual(line.jc_eac, 12000.0)
        self.assertAlmostEqual(line.jc_variance, 2000.0)
        self.assertEqual(line.jc_status, 'ok')
        # budget: remaining budget
        self.contract.costing_method = 'budget'
        line.invalidate_recordset()
        self.assertAlmostEqual(line.jc_etc, 9000.0)
        # manual
        self.contract.costing_method = 'manual'
        line.etc_manual = 11000.0
        line.invalidate_recordset()
        self.assertAlmostEqual(line.jc_eac, 16000.0)
        self.assertAlmostEqual(line.jc_variance, -2000.0)
        self.assertEqual(line.jc_status, 'over')
        self.contract.invalidate_recordset()
        self.assertEqual(self.contract.jc_alert_count, 1)

    def test_05_overheads_in_forecast(self):
        self._cost(500, product_id=self.rent.id)
        self.contract.invalidate_recordset()
        data = self.contract._jc_data()
        rows = {r['type']: r for r in data['rows']}
        self.assertIn('site_overhead', rows)
        self.assertEqual(rows['site_overhead']['actual'], 500.0)
        # head-office overhead budget = 5% of direct budget (14000 + 3500)
        self.assertAlmostEqual(rows['ho_overhead']['budget'], 875.0)
        self.assertTrue(self.contract.jc_summary_html)

    def test_06_overhead_allocation(self):
        other = self.contract.copy({'title': 'Second job'})
        other.action_confirm()
        self._cost(3000, product_id=self.cement.id)
        column = other._analytic_column()
        self.env['account.analytic.line'].create({
            'name': 'cost', 'amount': -1000, 'date': fields.Date.today(), column: other.analytic_account_id.id,
            'product_id': self.cement.id})
        alloc = self.env['dvz.overhead.allocation'].create({
            'amount': 800.0, 'basis': 'direct_cost',
            'contract_ids': [Command.set([self.contract.id, other.id])],
            'date_from': fields.Date.today().replace(day=1), 'date_to': fields.Date.today(),
        })
        alloc.action_compute()
        shares = {l.contract_id: l.amount for l in alloc.line_ids}
        self.assertAlmostEqual(shares[self.contract], 600.0)
        self.assertAlmostEqual(shares[other], 200.0)
        alloc.action_post()
        self.assertEqual(alloc.state, 'posted')
        lines = alloc.analytic_line_ids
        self.assertEqual(len(lines), 2)
        self.assertEqual(set(lines.mapped('dvz_cost_type')), {'ho_overhead'})
        self.assertEqual(lines.filtered(lambda l: l.dvz_contract_id == self.contract).amount, -600.0)
        alloc.action_cancel()
        self.assertFalse(alloc.analytic_line_ids)

    def test_07_report_view_and_pdf(self):
        self._cost(1000, product_id=self.cement.id, dvz_contract_line_id=self.concrete.id)
        self.env.flush_all()
        rows = self.env['dvz.job.cost.report'].search([('contract_id', '=', self.contract.id)])
        self.assertAlmostEqual(sum(rows.mapped('budget')), 17500.0 + 875.0)
        self.assertAlmostEqual(sum(rows.mapped('actual')), 1000.0)
        html = self.env['ir.actions.report']._render_qweb_html(
            'dvz_contract_costing.report_dvz_job_cost', self.contract.ids)[0]
        self.assertIn(b'Concrete works', html)

    def test_08_only_real_costs_count(self):
        """Revenue, customer-invoice and balance-sheet lines on the contract are not job costs;
        a manual analytic line that Odoo gives a default employee is not labour."""
        income = self.env['account.account'].create(
            {'name': 'Contract revenue adj', 'code': '419990', 'account_type': 'income'})
        advance = self.env['account.account'].create(
            {'name': 'Advances from clients', 'code': '219990', 'account_type': 'liability_current'})
        rev = self._cost(5000, general_account_id=income.id)
        adv = self._cost(700, general_account_id=advance.id)
        rent = self._cost(400, product_id=self.rent.id, employee_id=self.employee.id)
        self.assertFalse(rev.dvz_cost_type, 'Revenue reductions are not costs')
        self.assertFalse(adv.dvz_cost_type, 'Advance movements are not costs')
        self.assertEqual(rent.dvz_cost_type, 'site_overhead', 'Not a timesheet: no project, so not labour')
        self.contract.invalidate_recordset()
        self.assertEqual(self.contract.actual_cost, 400.0)
        self.assertEqual(self.contract.jc_actual, 400.0)
