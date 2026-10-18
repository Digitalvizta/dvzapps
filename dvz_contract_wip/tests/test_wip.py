from datetime import timedelta

from odoo import Command, fields
from odoo.exceptions import UserError
from odoo.tests import TransactionCase, tagged


@tagged('post_install', '-at_install')
class TestWip(TransactionCase):

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        company = cls.env.company
        Account = cls.env['account.account']

        def acc(code, name, atype):
            return Account.create({'code': code, 'name': name, 'account_type': atype})
        company.write({
            'dvz_analytic_per_contract': True,
            'dvz_wip_method': 'cost',
            'dvz_wip_journal_id': cls.env['account.journal'].create(
                {'name': 'WIP', 'code': 'WIPT', 'type': 'general'}).id,
            'dvz_wip_revenue_account_id': acc('409901', 'Contract revenue WIP', 'income').id,
            'dvz_wip_asset_account_id': acc('109901', 'Contract assets', 'asset_current').id,
            'dvz_wip_liability_account_id': acc('209901', 'Contract liabilities', 'liability_current').id,
            'dvz_wip_loss_account_id': acc('609901', 'Expected contract losses', 'expense').id,
            'dvz_wip_provision_account_id': acc('209902', 'Provision contract losses', 'liability_current').id,
        })
        client = cls.env['res.partner'].create({'name': 'Dammam Client'})
        cls.contract = cls.env['dvz.contract'].create({
            'title': 'School building', 'partner_id': client.id, 'costing_method': 'budget',
            'date_start': fields.Date.today() - timedelta(days=60),
            'line_ids': [Command.create({'name': 'Structure', 'quantity': 1, 'price_unit': 100000.0,
                                         'cost_material_unit': 80000.0})],
        })
        cls.contract.action_confirm()

    def _cost(self, amount):
        column = self.contract._analytic_column()
        self.env['account.analytic.line'].create({
            'name': 'cost', 'amount': -amount, 'date': fields.Date.today() - timedelta(days=1),
            column: self.contract.analytic_account_id.id, 'dvz_contract_line_id': self.contract.line_ids.id})

    def _run(self):
        run = self.env['dvz.wip.run'].create({'date': fields.Date.today()})
        run.action_compute()
        return run, run.line_ids.filtered(lambda l: l.contract_id == self.contract)

    def test_01_under_billing_entry_and_reversal(self):
        self._cost(20000.0)          # 20000 of 80000 forecast = 25 %
        run, line = self._run()
        self.assertAlmostEqual(line.percent, 25.0)
        self.assertAlmostEqual(line.earned, 25000.0)
        self.assertEqual(line.billed, 0.0)
        self.assertAlmostEqual(line.adjustment, 25000.0)
        self.assertEqual(line.position, 'under')
        run.action_post()
        self.assertEqual(run.state, 'posted')
        move = run.move_id
        self.assertEqual(move.state, 'posted')
        asset = self.env.company.dvz_wip_asset_account_id
        mine = move.line_ids.filtered(lambda l: l.partner_id == self.contract.partner_id)
        self.assertAlmostEqual(sum(mine.filtered(lambda l: l.account_id == asset).mapped('debit')), 25000.0)
        revenue_line = mine.filtered(lambda l: l.account_id == self.env.company.dvz_wip_revenue_account_id)
        self.assertEqual(revenue_line.analytic_distribution, {str(self.contract.analytic_account_id.id): 100.0})
        self.assertEqual(run.reversal_move_id.date, run.date + timedelta(days=1))
        self.assertEqual(run.reversal_move_id.reversed_entry_id, move)
        self.contract.invalidate_recordset()
        self.assertAlmostEqual(self.contract.wip_adjustment, 25000.0)
        run.action_cancel()
        self.assertEqual(move.state, 'cancel')

    def test_02_over_billing_and_manual(self):
        self._cost(10000.0)
        run, line = self._run()
        line.billed = 40000.0        # invoiced ahead of the work
        self.assertAlmostEqual(line.adjustment, 12500.0 - 40000.0)
        self.assertEqual(line.position, 'over')
        run.action_post()
        liability = self.env.company.dvz_wip_liability_account_id
        mine = run.move_id.line_ids.filtered(lambda l: l.partner_id == self.contract.partner_id)
        self.assertAlmostEqual(sum(mine.filtered(lambda l: l.account_id == liability).mapped('credit')), 27500.0)
        self.contract.write({'wip_method': 'manual', 'wip_percent_manual': 60.0})
        _run2, line2 = self._run()
        self.assertAlmostEqual(line2.percent, 60.0)

    def test_03_expected_loss_provision(self):
        self._cost(60000.0)
        # the forecast goes above the contract value: 60000 spent, and 60000 still to come
        self.contract.costing_method = 'manual'
        self.contract.line_ids.etc_manual = 60000.0
        run, line = self._run()
        self.assertAlmostEqual(line.forecast_cost, 120000.0)
        self.assertAlmostEqual(line.percent, 50.0)
        # expected loss 20000; 60000 cost - 50000 earned = 10000 already in P&L -> provide 10000
        self.assertAlmostEqual(line.loss_provision, 10000.0)
        run.action_post()
        prov = self.env.company.dvz_wip_provision_account_id
        mine = run.move_id.line_ids.filtered(lambda l: l.partner_id == self.contract.partner_id)
        self.assertAlmostEqual(sum(mine.filtered(lambda l: l.account_id == prov).mapped('credit')), 10000.0)

    def test_04_missing_settings(self):
        self.env.company.dvz_wip_asset_account_id = False
        self._cost(1000.0)
        run, _line = self._run()
        with self.assertRaises(UserError):
            run.action_post()

    def test_05_pdf(self):
        self._cost(1000.0)
        run, _line = self._run()
        html = self.env['ir.actions.report']._render_qweb_html('dvz_contract_wip.report_dvz_wip_run', run.ids)[0]
        self.assertIn(b'WIP Schedule', html)

    def test_06_handed_over_is_complete(self):
        self._cost(1000.0)
        self.contract.action_handover()
        _run, line = self._run()
        self.assertEqual(line.percent, 100.0)
        self.assertAlmostEqual(line.earned, 100000.0)
