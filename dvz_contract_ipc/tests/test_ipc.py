from odoo.exceptions import UserError
from odoo.tests import TransactionCase, tagged


@tagged("post_install", "-at_install")
class TestDvzIpc(TransactionCase):

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        company = cls.env.company
        company.dvz_ipc_approval_required = False
        company.dvz_retention_method = "track_only"
        cls.partner = cls.env["res.partner"].create({"name": "IPC Client"})
        cls.contract = cls.env["dvz.contract"].create({
            "title": "Warehouse",
            "partner_id": cls.partner.id,
            "retention_percent": 10.0,
            "tax_ids": [(6, 0, [])],
            "line_ids": [
                (0, 0, {"code": "A", "name": "Steel", "quantity": 100, "price_unit": 10}),
                (0, 0, {"code": "B", "name": "Roof", "quantity": 10, "price_unit": 100}),
            ],
        })
        cls.contract.action_confirm()

    def test_two_certificates(self):
        ipc1 = self.env["dvz.contract.ipc"].create({"contract_id": self.contract.id})
        self.assertEqual(len(ipc1.line_ids), 2)
        ipc1.line_ids[0].current_qty = 40
        self.assertEqual(ipc1.amount_gross, 400.0)
        self.assertEqual(ipc1.amount_retention, 40.0)
        ipc1.action_submit()
        self.assertEqual(ipc1.state, "approved")

        ipc2 = self.env["dvz.contract.ipc"].create({"contract_id": self.contract.id})
        self.assertEqual(ipc2.line_ids[0].previous_qty, 40)
        ipc2.line_ids[0].current_qty = 70
        with self.assertRaises(UserError):
            ipc2.action_submit()  # 110 > BOQ 100
        ipc2.line_ids[0].current_qty = 60
        ipc2.action_submit()
        self.assertEqual(self.contract.amount_certified, 1000.0)
        self.assertEqual(self.contract.retention_held, 100.0)

    def test_invoice(self):
        ipc = self.env["dvz.contract.ipc"].create({"contract_id": self.contract.id})
        ipc.line_ids[1].current_qty = 5
        ipc.action_submit()
        ipc.action_create_invoice()
        self.assertEqual(ipc.state, "invoiced")
        self.assertEqual(ipc.invoice_id.amount_untaxed, 500.0)
