from odoo.tests import TransactionCase, tagged


@tagged("post_install", "-at_install")
class TestDvzSubcontract(TransactionCase):

    def test_vendor_bill(self):
        self.env.company.write({"dvz_ipc_approval_required": False, "dvz_retention_method": "track_only"})
        client = self.env["res.partner"].create({"name": "Owner"})
        sub_partner = self.env["res.partner"].create({"name": "MEP Sub"})
        main = self.env["dvz.contract"].create({
            "title": "Hospital", "partner_id": client.id,
            "line_ids": [(0, 0, {"name": "All works", "quantity": 1, "price_unit": 100000})],
        })
        main.action_confirm()
        sub = self.env["dvz.contract"].with_context(default_contract_type="subcontract").create({
            "title": "MEP", "partner_id": sub_partner.id, "contract_type": "subcontract",
            "parent_contract_id": main.id, "tax_ids": [(6, 0, [])],
            "line_ids": [(0, 0, {"name": "MEP works", "quantity": 1, "price_unit": 30000})],
        })
        self.assertTrue(sub.name.startswith("SUB/"))
        sub.action_confirm()
        self.assertEqual(sub.analytic_account_id, main.analytic_account_id)
        self.assertEqual(main.subcontract_amount, 30000.0)
        ipc = self.env["dvz.contract.ipc"].create({"contract_id": sub.id})
        ipc.line_ids.current_qty = 0.5
        ipc.action_submit()
        ipc.action_create_invoice()
        self.assertEqual(ipc.invoice_id.move_type, "in_invoice")
