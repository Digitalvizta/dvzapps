import base64

from odoo import Command, fields
from odoo.exceptions import UserError, ValidationError
from odoo.tests import TransactionCase, tagged
from odoo.tools import mute_logger

PNG = base64.b64encode(bytes.fromhex(
    '89504e470d0a1a0a0000000d4948445200000001000000010806000000'
    '1f15c4890000000d49444154789c6360f8cf000000030101005c5b8d6e0000000049454e44ae426082'))


@tagged('post_install', '-at_install')
class TestSiteDiary(TransactionCase):

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.env.company.write({'dvz_analytic_per_contract': True, 'dvz_diary_approval': True})
        client = cls.env['res.partner'].create({'name': 'Jeddah Owner'})
        cls.mason = cls.env['product.product'].create(
            {'name': 'Mason', 'type': 'service', 'dvz_cost_type': 'labour', 'standard_price': 15.0})
        cls.excavator = cls.env['product.product'].create(
            {'name': 'Excavator', 'type': 'service', 'dvz_cost_type': 'equipment', 'standard_price': 120.0})
        cls.contract = cls.env['dvz.contract'].create({
            'title': 'Warehouse', 'partner_id': client.id,
            'line_ids': [Command.create({'item_no': '2.1', 'name': 'Excavation', 'quantity': 1000, 'price_unit': 30.0,
                                         'cost_labour_unit': 5.0, 'cost_equipment_unit': 10.0})],
        })
        cls.contract.action_confirm()
        cls.boq = cls.contract.line_ids

    def _diary(self, date=None, **vals):
        return self.env['dvz.site.diary'].create(dict({
            'contract_id': self.contract.id,
            'date': date or fields.Date.today(),
            'weather': 'hot',
            'manpower_ids': [
                Command.create({'product_id': self.mason.id, 'headcount': 6, 'hours': 8, 'rate': 15.0,
                                'contract_line_id': self.boq.id}),
                Command.create({'product_id': self.mason.id, 'headcount': 4, 'hours': 8, 'rate': 15.0,
                                'subcontractor_id': self.env['res.partner'].create({'name': 'Sub Co'}).id}),
            ],
            'equipment_ids': [Command.create({'product_id': self.excavator.id, 'quantity': 1, 'hours_working': 7,
                                              'hours_idle': 1, 'rate': 120.0, 'contract_line_id': self.boq.id})],
            'work_ids': [Command.create({'contract_line_id': self.boq.id, 'description': 'Excavation zone A',
                                         'quantity': 150})],
            'delay_ids': [Command.create({'cause': 'weather', 'responsible': 'neutral', 'hours_lost': 2,
                                          'description': 'Sandstorm'})],
            'photo_ids': [Command.create({'image': PNG, 'caption': 'Zone A'})],
        }, **vals))

    def test_01_totals_and_approval_post_costs(self):
        diary = self._diary()
        self.assertEqual(diary.manpower_count, 10)
        self.assertEqual(diary.labour_hours, 80)
        self.assertEqual(diary.labour_cost, 720.0, 'Subcontractor crew is not costed')
        self.assertEqual(diary.equipment_cost, 840.0)
        diary.action_submit()
        self.assertEqual(diary.state, 'submitted')
        diary.action_approve()
        self.assertEqual(diary.state, 'approved')
        lines = diary.analytic_line_ids
        self.assertEqual(len(lines), 2)
        labour = lines.filtered(lambda l: l.dvz_cost_type == 'labour')
        equip = lines.filtered(lambda l: l.dvz_cost_type == 'equipment')
        self.assertEqual(labour.amount, -720.0)
        self.assertEqual(labour.dvz_contract_line_id, self.boq)
        self.assertEqual(labour.dvz_contract_id, self.contract)
        self.assertEqual(equip.amount, -840.0)
        self.boq.invalidate_recordset()
        self.assertEqual(self.boq.jc_actual, 1560.0, 'Diary costs show in job costing')
        self.assertEqual(self.boq.jc_actual_hours, 48.0)
        self.contract.invalidate_recordset()
        self.assertEqual(self.contract.diary_hours_lost_client, 2.0)
        with self.assertRaises(UserError):
            diary.notes = 'changed after approval'
        diary.action_draft()
        self.assertFalse(diary.analytic_line_ids, 'Reset removes the posted costs')

    def test_02_settings_and_rules(self):
        self.env.company.write({'dvz_diary_post_labour': False, 'dvz_diary_approval': False})
        diary = self._diary()
        diary.action_submit()
        self.assertEqual(diary.state, 'approved', 'Without approval step, submit approves')
        self.assertEqual(diary.analytic_line_ids.mapped('dvz_cost_type'), ['equipment'])
        with self.assertRaises(Exception), mute_logger('odoo.sql_db'), self.cr.savepoint():
            self._diary()   # same contract, date and shift
        with self.assertRaises(ValidationError):
            self._diary(date=fields.Date.add(fields.Date.today(), days=2))

    def test_03_copy_previous_and_quantities(self):
        first = self._diary(date=fields.Date.add(fields.Date.today(), days=-1))
        first.action_submit()
        first.action_approve()
        today = self.env['dvz.site.diary'].create({'contract_id': self.contract.id})
        today.action_copy_previous()
        self.assertEqual(len(today.manpower_ids), 2)
        self.assertEqual(len(today.equipment_ids), 1)
        today.work_ids = [Command.create({'contract_line_id': self.boq.id, 'description': 'Zone B', 'quantity': 100})]
        self.assertEqual(today.work_ids.qty_to_date, 250.0)
        self.assertAlmostEqual(today.work_ids.percent_to_date, 25.0)

    def test_04_pdf(self):
        diary = self._diary()
        html = self.env['ir.actions.report']._render_qweb_html(
            'dvz_contract_site_diary.report_dvz_site_diary', diary.ids)[0]
        self.assertIn(b'Daily Site Report', html)
        self.assertIn(b'Sandstorm', html)
