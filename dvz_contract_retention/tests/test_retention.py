from odoo.tests import TransactionCase, tagged


@tagged("post_install", "-at_install")
class TestDvzRetention(TransactionCase):

    def test_handover_release(self):
        company = self.env.company
        company.write({"dvz_ipc_approval_required": False, "dvz_retention_method": "track_only",
                       "dvz_release_auto_on_handover": True, "dvz_release_handover_percent": 50.0})
        partner = self.env["res.partner"].create({"name": "Ret Client"})
        contract = self.env["dvz.contract"].create({
            "title": "School", "partner_id": partner.id, "retention_percent": 10.0,
            "line_ids": [(0, 0, {"name": "Works", "quantity": 1, "price_unit": 10000})],
        })
        contract.action_confirm()
        ipc = self.env["dvz.contract.ipc"].create({"contract_id": contract.id})
        ipc.line_ids.current_qty = 1
        ipc.action_submit()
        self.assertEqual(contract.retention_held, 1000.0)
        contract.action_handover()
        release = contract.retention_release_ids
        self.assertEqual(len(release), 1)
        self.assertEqual(release.amount, 500.0)
        release.method = "track_only"
        release.action_release()
        self.assertEqual(contract.retention_balance, 500.0)
