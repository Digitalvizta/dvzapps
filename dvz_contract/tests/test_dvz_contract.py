from odoo.exceptions import UserError
from odoo.tests import TransactionCase, tagged


@tagged("post_install", "-at_install")
class TestDvzContract(TransactionCase):

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.partner = cls.env["res.partner"].create({"name": "Test Client"})
        cls.contract = cls.env["dvz.contract"].create({
            "title": "Villa works",
            "partner_id": cls.partner.id,
            "advance_percent": 10.0,
            "line_ids": [
                (0, 0, {"display_type": "line_section", "name": "Civil"}),
                (0, 0, {"code": "1.1", "name": "Excavation", "quantity": 100, "price_unit": 50, "cost_price": 30}),
                (0, 0, {"code": "1.2", "name": "Concrete", "quantity": 20, "price_unit": 500, "cost_price": 350}),
            ],
        })

    def test_amounts(self):
        c = self.contract
        self.assertNotEqual(c.name, "New")
        self.assertEqual(c.amount_total, 15000.0)
        self.assertEqual(c.cost_budget, 10000.0)
        self.assertEqual(c.margin_planned, 5000.0)
        self.assertEqual(c.advance_amount, 1500.0)
        self.assertEqual(c.line_count, 2)

    def test_flow(self):
        c = self.contract
        c.action_confirm()
        self.assertEqual(c.state, "running")
        if c.company_id.dvz_auto_analytic:
            self.assertTrue(c.analytic_account_id)
        c.action_handover()
        self.assertEqual(c.state, "handover")
        self.assertTrue(c.date_handover)
        self.assertTrue(c.date_dlp_end)
        with self.assertRaises(UserError):
            c.unlink()

    def test_confirm_needs_boq(self):
        empty = self.env["dvz.contract"].create({"title": "Empty", "partner_id": self.partner.id})
        with self.assertRaises(UserError):
            empty.action_confirm()
