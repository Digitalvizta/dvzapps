from odoo import _, api, fields, models
from odoo.exceptions import UserError


class DvzContractLine(models.Model):
    _inherit = "dvz.contract.line"

    variation_id = fields.Many2one("dvz.contract.variation", string="Variation", readonly=True, index="btree_not_null")


class DvzContract(models.Model):
    _inherit = "dvz.contract"

    variation_ids = fields.One2many("dvz.contract.variation", "contract_id")
    variation_count = fields.Integer(compute="_compute_variation_figures")
    variation_pending_amount = fields.Monetary(
        string="Pending variations", compute="_compute_variation_figures",
        help="Submitted and approved variations not yet applied to the BOQ.")

    @api.depends("variation_ids.state", "variation_ids.amount_total")
    def _compute_variation_figures(self):
        for contract in self:
            contract.variation_count = len(contract.variation_ids)
            contract.variation_pending_amount = sum(contract.variation_ids.filtered(
                lambda v: v.state in ("submitted", "approved")).mapped("amount_total"))

    def _check_can_cancel(self):
        res = super()._check_can_cancel()
        if self.variation_ids.filtered(lambda v: v.state == "applied"):
            raise UserError(_("This contract has applied variations."))
        return res

    def action_new_variation(self):
        self.ensure_one()
        return {
            "type": "ir.actions.act_window",
            "res_model": "dvz.contract.variation",
            "view_mode": "form",
            "context": {"default_contract_id": self.id},
        }

    def action_view_variations(self):
        self.ensure_one()
        action = self.env["ir.actions.actions"]._for_xml_id("dvz_contract_variation.action_dvz_contract_variation")
        action["domain"] = [("contract_id", "=", self.id)]
        action["context"] = {"default_contract_id": self.id}
        return action
