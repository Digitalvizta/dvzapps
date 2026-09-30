from odoo import _, api, fields, models
from odoo.exceptions import UserError

BILLED_STATES = ("approved", "invoiced")


class DvzContract(models.Model):
    _inherit = "dvz.contract"

    ipc_ids = fields.One2many("dvz.contract.ipc", "contract_id", string="Payment certificates")
    ipc_count = fields.Integer(compute="_compute_ipc_figures")
    amount_certified = fields.Monetary(
        string="Certified to date", compute="_compute_ipc_figures",
        help="Gross value of approved and invoiced certificates.")
    certified_percent = fields.Float(string="Certified (%)", compute="_compute_ipc_figures")
    retention_held = fields.Monetary(
        string="Retention held", compute="_compute_ipc_figures",
        help="Retention withheld on approved and invoiced certificates.")
    advance_invoice_id = fields.Many2one("account.move", string="Advance invoice", copy=False, readonly=True)
    advance_recovered = fields.Monetary(string="Advance recovered", compute="_compute_ipc_figures")
    advance_remaining = fields.Monetary(string="Advance to recover", compute="_compute_ipc_figures")
    invoice_count = fields.Integer(compute="_compute_ipc_figures")

    @api.depends("ipc_ids.state", "ipc_ids.amount_gross", "ipc_ids.amount_retention",
                 "ipc_ids.amount_advance_recovery", "amount_total", "advance_amount", "advance_invoice_id")
    def _compute_ipc_figures(self):
        for contract in self:
            billed = contract.ipc_ids.filtered(lambda i: i.state in BILLED_STATES)
            contract.ipc_count = len(contract.ipc_ids)
            contract.amount_certified = sum(billed.mapped("amount_gross"))
            contract.certified_percent = (
                contract.amount_certified / contract.amount_total * 100.0 if contract.amount_total else 0.0)
            contract.retention_held = sum(billed.mapped("amount_retention"))
            recovered = sum(billed.mapped("amount_advance_recovery"))
            contract.advance_recovered = recovered
            contract.advance_remaining = max(contract.advance_amount - recovered, 0.0)
            contract.invoice_count = len(contract._get_dvz_invoices())

    # ------------------------------------------------------------------
    # Accounting configuration (overridden by the subcontract module)
    # ------------------------------------------------------------------
    def _get_dvz_accounts(self):
        """Return the accounting setup used to invoice this contract."""
        self.ensure_one()
        company = self.company_id
        product = company.dvz_progress_product_id or self.env.ref(
            "dvz_contract_ipc.product_progress_billing", raise_if_not_found=False)
        journal = company.dvz_ipc_journal_id or self.env["account.journal"].search([
            *self.env["account.journal"]._check_company_domain(company),
            ("type", "=", "sale"),
        ], limit=1)
        return {
            "move_type": "out_invoice",
            "journal": journal,
            "product": product,
            "progress_account": company.dvz_progress_account_id,
            "retention_account": company.dvz_retention_account_id,
            "advance_account": company.dvz_advance_account_id,
            "deduction_account": company.dvz_deduction_account_id,
        }

    def _get_dvz_invoices(self):
        self.ensure_one()
        return self.ipc_ids.mapped("invoice_id") | self.advance_invoice_id

    def _check_can_cancel(self):
        res = super()._check_can_cancel()
        for contract in self:
            if contract.ipc_ids.filtered(lambda i: i.state != "cancel"):
                raise UserError(_("Cancel the payment certificates of %s first.", contract.display_name))
            if contract.advance_invoice_id and contract.advance_invoice_id.state == "posted":
                raise UserError(_("Reverse the advance invoice of %s first.", contract.display_name))
        return res

    # ------------------------------------------------------------------
    # Actions
    # ------------------------------------------------------------------
    def action_new_ipc(self):
        self.ensure_one()
        if self.state != "running":
            raise UserError(_("Payment certificates can only be created for contracts in progress."))
        ipc = self.env["dvz.contract.ipc"].create({"contract_id": self.id})
        return {
            "type": "ir.actions.act_window",
            "res_model": "dvz.contract.ipc",
            "res_id": ipc.id,
            "view_mode": "form",
            "target": "current",
        }

    def action_view_ipcs(self):
        self.ensure_one()
        action = self.env["ir.actions.actions"]._for_xml_id("dvz_contract_ipc.action_dvz_contract_ipc")
        action["domain"] = [("contract_id", "=", self.id)]
        action["context"] = {"default_contract_id": self.id}
        return action

    def action_view_invoices(self):
        self.ensure_one()
        invoices = self._get_dvz_invoices()
        return {
            "type": "ir.actions.act_window",
            "name": _("Invoices"),
            "res_model": "account.move",
            "view_mode": "list,form",
            "domain": [("id", "in", invoices.ids)],
        }

    def action_create_advance_invoice(self):
        self.ensure_one()
        if self.advance_invoice_id and self.advance_invoice_id.state != "cancel":
            raise UserError(_("An advance invoice already exists for this contract."))
        if self.advance_amount <= 0:
            raise UserError(_("Set an advance payment on the contract first."))
        acc = self._get_dvz_accounts()
        if not acc["advance_account"]:
            raise UserError(_("Set the advance account in Settings > Contracting."))
        taxed = self.company_id.dvz_advance_invoice_taxed
        move = self.env["account.move"].with_company(self.company_id).create({
            "move_type": acc["move_type"],
            "partner_id": self.partner_id.id,
            "journal_id": acc["journal"].id if acc["journal"] else False,
            "currency_id": self.currency_id.id,
            "invoice_origin": self.name,
            "ref": _("Advance payment %s", self.name),
            "invoice_date": fields.Date.context_today(self),
            "dvz_contract_id": self.id,
            "invoice_line_ids": [(0, 0, {
                "name": _("Advance payment - %(contract)s - %(title)s", contract=self.name, title=self.title),
                "quantity": 1.0,
                "price_unit": self.advance_amount,
                "account_id": acc["advance_account"].id,
                "tax_ids": [(6, 0, self.tax_ids.ids if taxed else [])],
            })],
        })
        self.advance_invoice_id = move
        if self.company_id.dvz_ipc_auto_post:
            move.action_post()
        return {
            "type": "ir.actions.act_window",
            "res_model": "account.move",
            "res_id": move.id,
            "view_mode": "form",
        }
