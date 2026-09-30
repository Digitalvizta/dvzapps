from odoo.tests import TransactionCase, tagged


@tagged("post_install", "-at_install")
class TestDvzVariation(TransactionCase):

    def test_apply(self):
        self.env.company.write({"dvz_vo_approval_required": False, "dvz_vo_auto_apply": True})
        partner = self.env["res.partner"].create({"name": "VO Client"})
        contract = self.env["dvz.contract"].create({
            "title": "Mall", "partner_id": partner.id,
            "line_ids": [(0, 0, {"code": "1", "name": "Tiles", "quantity": 100, "price_unit": 20})],
        })
        contract.action_confirm()
        vo = self.env["dvz.contract.variation"].create({
            "contract_id": contract.id, "title": "Extra",
            "line_ids": [
                (0, 0, {"change_type": "add", "name": "Skirting", "quantity": 50, "price_unit": 10}),
                (0, 0, {"change_type": "adjust", "contract_line_id": contract.line_ids[0].id,
                        "name": "Tiles", "quantity_change": 10, "price_unit": 20}),
            ],
        })
        self.assertEqual(vo.amount_total, 700.0)
        vo.action_submit()
        self.assertEqual(vo.state, "applied")
        self.assertEqual(contract.amount_original, 2000.0)
        self.assertEqual(contract.amount_variation, 700.0)
        self.assertEqual(contract.amount_total, 2700.0)
