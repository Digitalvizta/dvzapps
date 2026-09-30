from odoo import _, api, fields, models
from odoo.exceptions import ValidationError


class DvzContract(models.Model):
    _inherit = "dvz.contract"

    parent_contract_id = fields.Many2one(
        "dvz.contract", string="Main contract", index="btree_not_null", tracking=True, check_company=True,
        domain="[('contract_type', '=', 'customer')]")
    subcontract_ids = fields.One2many("dvz.contract", "parent_contract_id", string="Subcontracts")
    subcontract_count = fields.Integer(compute="_compute_subcontract_figures")
    subcontract_amount = fields.Monetary(
        string="Subcontracted value", compute="_compute_subcontract_figures",
        help="Value of confirmed subcontracts under this contract.")

    @api.depends("subcontract_ids.amount_total", "subcontract_ids.state")
    def _compute_subcontract_figures(self):
        for contract in self:
            subs = contract.subcontract_ids.filtered(lambda s: s.state not in ("draft", "cancel"))
            contract.subcontract_count = len(contract.subcontract_ids)
            contract.subcontract_amount = sum(subs.mapped("amount_total"))

    @api.constrains("parent_contract_id", "contract_type")
    def _check_parent(self):
        for contract in self:
            if contract.parent_contract_id and contract.contract_type != "subcontract":
                raise ValidationError(_("Only subcontracts can be linked to a main contract."))

    @api.onchange("parent_contract_id")
    def _onchange_parent_contract_id(self):
        parent = self.parent_contract_id
        if parent:
            self.project_id = parent.project_id
            if self.company_id.dvz_sub_inherit_analytic:
                self.analytic_account_id = parent.analytic_account_id
            if not self.date_start:
                self.date_start = parent.date_start
            if not self.date_end:
                self.date_end = parent.date_end

    def _ensure_analytic_account(self):
        for contract in self:
            parent = contract.parent_contract_id
            if (not contract.analytic_account_id and parent and contract.company_id.dvz_sub_inherit_analytic):
                parent._ensure_analytic_account()
                contract.analytic_account_id = parent.analytic_account_id
        return super()._ensure_analytic_account()

    def _get_dvz_accounts(self):
        res = super()._get_dvz_accounts()
        if self.contract_type != "subcontract":
            return res
        company = self.company_id
        journal = company.dvz_sub_journal_id or self.env["account.journal"].search([
            *self.env["account.journal"]._check_company_domain(company),
            ("type", "=", "purchase"),
        ], limit=1)
        res.update({
            "move_type": "in_invoice",
            "journal": journal,
            "product": company.dvz_sub_product_id or res["product"],
            "progress_account": company.dvz_sub_expense_account_id,
            "retention_account": company.dvz_sub_retention_account_id,
            "advance_account": company.dvz_sub_advance_account_id,
            "deduction_account": company.dvz_sub_deduction_account_id,
        })
        return res

    def action_view_subcontracts(self):
        self.ensure_one()
        action = self.env["ir.actions.actions"]._for_xml_id("dvz_contract_subcontract.action_dvz_subcontract")
        action["domain"] = [("parent_contract_id", "=", self.id)]
        action["context"] = {
            "default_contract_type": "subcontract",
            "default_parent_contract_id": self.id,
            "default_project_id": self.project_id.id,
        }
        return action

    def action_new_subcontract(self):
        self.ensure_one()
        return {
            "type": "ir.actions.act_window",
            "res_model": "dvz.contract",
            "view_mode": "form",
            "views": [(self.env.ref("dvz_contract_subcontract.dvz_subcontract_view_form").id, "form")],
            "context": {
                "default_contract_type": "subcontract",
                "default_parent_contract_id": self.id,
                "default_project_id": self.project_id.id,
                "default_analytic_account_id": self.analytic_account_id.id,
            },
        }
