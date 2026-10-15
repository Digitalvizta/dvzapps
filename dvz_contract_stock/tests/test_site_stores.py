from odoo import Command
from odoo.exceptions import UserError
from odoo.tests import TransactionCase, tagged


@tagged('post_install', '-at_install')
class TestSiteStores(TransactionCase):

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.company = cls.env.company
        cls.warehouse = cls.env['stock.warehouse'].search([('company_id', '=', cls.company.id)], limit=1)
        cls.main = cls.warehouse.lot_stock_id
        cls.vendor = cls.env['res.partner'].create({'name': 'Cement Supplier'})
        cls.client = cls.env['res.partner'].create({'name': 'Riyadh Developer'})
        cls.cement = cls.env['product.product'].create({
            'name': 'Cement bag 50kg', 'type': 'consu', 'is_storable': True, 'standard_price': 20.0,
            'purchase_ok': True,
            'seller_ids': [Command.create({'partner_id': cls.vendor.id, 'price': 20.0})],
        })
        cls.contract_a = cls._make_contract('Villa A')
        cls.contract_b = cls._make_contract('Villa B')

    @classmethod
    def _make_contract(cls, title):
        return cls.env['dvz.contract'].create({
            'title': title,
            'partner_id': cls.client.id,
            'line_ids': [Command.create({
                'item_no': '1.1', 'name': 'Concrete works', 'product_id': cls.cement.id,
                'quantity': 100, 'price_unit': 50.0, 'cost_unit': 30.0,
            })],
        })

    # ------------------------------------------------------------------ helpers
    def _features(self, site_stores=False, transfer=False, usage=False, **company_vals):
        employee = self.env.ref('base.group_user')
        for key, on in (('group_dvz_site_stores', site_stores), ('group_dvz_site_transfer', transfer),
                        ('group_dvz_material_usage', usage)):
            group = self.env.ref('dvz_contract_stock.%s' % key)
            employee.write({'implied_ids': [Command.link(group.id) if on else Command.unlink(group.id)]})
        if company_vals:
            self.company.write(company_vals)

    def _put_in_main_store(self, qty):
        self.env['stock.quant']._update_available_quantity(self.cement, self.main, qty)

    def _qty(self, location):
        return self.cement.with_context(location=location.id).qty_available

    def _done(self, picking):
        for move in picking.move_ids:
            move.quantity = move.product_uom_qty
            move.picked = True
        picking._action_done()

    def _analytic(self, contract):
        column = contract._analytic_column()
        lines = self.env['account.analytic.line'].search([(column, '=', contract.analytic_account_id.id),
                                                          ('dvz_stock_move_id', '!=', False)])
        return sum(lines.mapped('amount'))

    def _request(self, contract, qty):
        request = self.env['dvz.material.request'].create({
            'contract_id': contract.id,
            'line_ids': [Command.create({'product_id': self.cement.id, 'quantity': qty,
                                         'contract_line_id': contract.line_ids[0].id})],
        })
        request.action_submit()
        if request.state == 'submitted':
            request.action_approve()
        return request

    # ------------------------------------------------------------------ tests
    def test_01_all_off_behaves_like_before(self):
        self._features(site_stores=False, dvz_mr_check_stock=True)
        self.contract_a.action_confirm()
        self.assertFalse(self.contract_a.site_location_id, 'No site store when the feature is off')
        request = self._request(self.contract_a, 10)
        self.assertFalse(request.dvz_check_stock, 'Stock check needs site stores')
        request.action_create_rfq()
        po = request.purchase_ids
        self.assertEqual(po.order_line.product_qty, 10)
        po.button_confirm()
        self.assertEqual(po.picking_ids.location_dest_id, self.main, 'Delivered to the main warehouse')

    def test_02_site_store_and_delivery_to_site(self):
        self._features(site_stores=True, dvz_site_deliver=True)
        self.contract_a.action_confirm()
        site = self.contract_a.site_location_id
        self.assertTrue(site)
        self.assertEqual(site.dvz_site_contract_id, self.contract_a)
        request = self._request(self.contract_a, 10)
        request.action_create_rfq()
        po = request.purchase_ids
        po.button_confirm()
        receipt = po.picking_ids
        self.assertEqual(receipt.location_dest_id, site, 'Contract purchases go to the site store')
        self._done(receipt)
        self.assertEqual(self._qty(site), 10)
        self.assertEqual(self.contract_a.site_quant_count, 1)
        self.assertAlmostEqual(self.contract_a.site_stock_value, 200.0)

    def test_03_check_stock_takes_store_then_buys_rest(self):
        self._features(site_stores=True, dvz_mr_check_stock=True, dvz_charge_store_issue=True)
        self._put_in_main_store(30)
        self.contract_a.action_confirm()
        request = self._request(self.contract_a, 50)
        line = request.line_ids
        self.assertTrue(request.dvz_check_stock)
        self.assertEqual(line.qty_from_stock, 30)
        self.assertEqual(line.qty_to_buy, 20)
        request.action_create_rfq()
        self.assertEqual(request.state, 'ordered')
        picking = request.dvz_picking_ids
        self.assertEqual(len(picking), 1)
        self.assertEqual(picking.move_ids.product_uom_qty, 30)
        self.assertEqual(request.purchase_ids.order_line.product_qty, 20)
        self._done(picking)
        site = self.contract_a.site_location_id
        self.assertEqual(self._qty(site), 30)
        self.assertEqual(self._qty(self.main), 0)
        self.assertAlmostEqual(self._analytic(self.contract_a), -600.0, msg='30 x 20 charged to the project')

    def test_04_user_can_choose_to_buy_everything(self):
        self._features(site_stores=True, dvz_mr_check_stock=True)
        self._put_in_main_store(30)
        self.contract_a.action_confirm()
        request = self._request(self.contract_a, 10)
        request.line_ids.qty_from_stock = 0
        request.action_dvz_process()
        self.assertFalse(request.dvz_picking_ids)
        self.assertEqual(request.purchase_ids.order_line.product_qty, 10)

    def test_05_store_has_nothing_buys_all(self):
        self._features(site_stores=True, dvz_mr_check_stock=True)
        self.contract_a.action_confirm()
        request = self._request(self.contract_a, 10)
        self.assertEqual(request.line_ids.qty_from_stock, 0)
        request.action_dvz_process()
        self.assertFalse(request.dvz_picking_ids)
        self.assertEqual(request.purchase_ids.order_line.product_qty, 10)

    def test_06_transfer_between_sites_moves_cost(self):
        self._features(site_stores=True, transfer=True)
        (self.contract_a | self.contract_b).action_confirm()
        site_a, site_b = self.contract_a.site_location_id, self.contract_b.site_location_id
        self.env['stock.quant']._update_available_quantity(self.cement, site_a, 10)
        picking = self.env['stock.picking'].with_context(
            **self.contract_a._dvz_transfer_context(dest=site_b)).create({
                'move_ids': [Command.create({
                    'product_id': self.cement.id, 'product_uom_qty': 4, 'product_uom': self.cement.uom_id.id,
                    'location_id': site_a.id, 'location_dest_id': site_b.id})],
            })
        self.assertEqual(picking.location_id, site_a)
        self.assertEqual(picking.location_dest_id, site_b)
        picking.action_confirm()
        picking.action_assign()
        self._done(picking)
        self.assertEqual(self._qty(site_a), 6)
        self.assertEqual(self._qty(site_b), 4)
        self.assertAlmostEqual(self._analytic(self.contract_a), 80.0, msg='Site A credited 4 x 20')
        self.assertAlmostEqual(self._analytic(self.contract_b), -80.0, msg='Site B charged 4 x 20')

    def test_07_return_leftovers_to_store_credits_project(self):
        self._features(site_stores=True, transfer=True, dvz_charge_store_issue=True)
        self.contract_a.action_confirm()
        site = self.contract_a.site_location_id
        self.env['stock.quant']._update_available_quantity(self.cement, site, 7)
        action = self.contract_a.action_dvz_return_leftovers()
        picking = self.env['stock.picking'].browse(action['res_id'])
        self.assertEqual(picking.location_dest_id, self.main)
        self._done(picking)
        self.assertEqual(self._qty(site), 0)
        self.assertEqual(self._qty(self.main), 7)
        self.assertAlmostEqual(self._analytic(self.contract_a), 140.0)

    def test_08_no_store_charge_when_setting_off(self):
        self._features(site_stores=True, dvz_mr_check_stock=True, dvz_charge_store_issue=False)
        self._put_in_main_store(10)
        self.contract_a.action_confirm()
        request = self._request(self.contract_a, 10)
        request.action_dvz_process()
        self._done(request.dvz_picking_ids)
        self.assertEqual(self._qty(self.contract_a.site_location_id), 10)
        self.assertAlmostEqual(self._analytic(self.contract_a), 0.0)

    def test_09_material_usage(self):
        self._features(site_stores=True, usage=True)
        self.contract_a.action_confirm()
        site = self.contract_a.site_location_id
        self.env['stock.quant']._update_available_quantity(self.cement, site, 10)
        boq = self.contract_a.line_ids[0]
        usage = self.env['dvz.material.usage'].create({
            'contract_id': self.contract_a.id,
            'line_ids': [
                Command.create({'product_id': self.cement.id, 'quantity': 4, 'contract_line_id': boq.id}),
                Command.create({'product_id': self.cement.id, 'quantity': 1, 'contract_line_id': boq.id,
                                'usage_type': 'wastage'}),
            ],
        })
        self.assertTrue(usage.name.startswith('MU/'))
        usage.action_done()
        self.assertEqual(usage.state, 'done')
        self.assertEqual(self._qty(site), 5)
        self.assertAlmostEqual(boq.material_used_cost, 80.0)
        self.assertAlmostEqual(boq.material_waste_cost, 20.0)
        self.assertAlmostEqual(self.contract_a.material_used_cost, 80.0)
        self.assertAlmostEqual(self._analytic(self.contract_a), 0.0, msg='Usage does not post cost twice')
        usage.action_cancel()
        self.assertEqual(self._qty(site), 10, 'Cancelling puts the material back on site')
        self.assertAlmostEqual(boq.material_used_cost, 0.0)

    def test_10_usage_blocked_when_not_enough_or_switched_off(self):
        self._features(site_stores=True, usage=True)
        self.contract_a.action_confirm()
        self.env['stock.quant']._update_available_quantity(self.cement, self.contract_a.site_location_id, 2)
        usage = self.env['dvz.material.usage'].create({
            'contract_id': self.contract_a.id,
            'line_ids': [Command.create({'product_id': self.cement.id, 'quantity': 5})],
        })
        with self.assertRaises(UserError):
            usage.action_done()
        usage.line_ids.quantity = 1
        self._features(site_stores=True, usage=False)
        with self.assertRaises(UserError):
            usage.action_done()

    def test_11_supplier_return_reduces_ordered_cost(self):
        self._features(site_stores=True, dvz_returns_reduce_budget=True)
        self.contract_a.action_confirm()
        request = self._request(self.contract_a, 10)
        request.action_create_rfq()
        po = request.purchase_ids
        po.button_confirm()
        receipt = po.picking_ids
        self._done(receipt)
        boq = self.contract_a.line_ids[0]
        self.assertAlmostEqual(boq.cost_committed, 200.0)
        wizard = self.env['stock.return.picking'].with_context(
            active_id=receipt.id, active_model='stock.picking').create({})
        wizard.product_return_moves.quantity = 3
        res = wizard.action_create_returns()
        ret = self.env['stock.picking'].browse(res['res_id'])
        self._done(ret)
        boq.invalidate_recordset()
        self.assertAlmostEqual(boq.cost_committed, 140.0, msg='3 returned x 20 taken off')
        self.company.dvz_returns_reduce_budget = False
        boq._compute_procurement()
        self.assertAlmostEqual(boq.cost_committed, 200.0)

    def test_12_settings_screen_switches(self):
        settings = self.env['res.config.settings'].create({
            'group_dvz_site_stores': True, 'group_dvz_site_transfer': True, 'group_dvz_material_usage': True,
        })
        settings.execute()
        self.assertTrue(self.company._dvz_feature('site_stores'))
        self.assertTrue(self.company._dvz_feature('material_usage'))
        settings = self.env['res.config.settings'].create({
            'group_dvz_site_stores': False, 'group_dvz_site_transfer': True, 'group_dvz_material_usage': True,
        })
        settings.execute()
        self.assertFalse(self.company._dvz_feature('site_stores'))
        self.assertFalse(self.company._dvz_feature('site_transfer'), 'Sub-features follow the main switch')
        self.assertFalse(self.company._dvz_feature('material_usage'))
