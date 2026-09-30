from dateutil.relativedelta import relativedelta

from odoo import _, api, fields, models
from odoo.exceptions import UserError, ValidationError


class DvContract(models.Model):
    _name = "dvz.contract"
    _description = "Contract"
    _inherit = ["mail.thread", "mail.activity.mixin"]
    _order = "date_signed desc, id desc"
    _check_company_auto = True

    # ------------------------------------------------------------------
    # Identification
    # ------------------------------------------------------------------
    name = fields.Char(
        string="Number", required=True, copy=False, readonly=True,
        default=lambda self: _("New"), tracking=True)
    title = fields.Char(string="Contract title", required=True, tracking=True)
    contract_type = fields.Selection(
        [("customer", "Client contract"), ("subcontract", "Subcontract")],
        string="Type", default="customer", required=True, tracking=True, index=True)
    partner_id = fields.Many2one(
        "res.partner", string="Client", required=True, tracking=True, check_company=True)
    company_id = fields.Many2one(
        "res.company", required=True, index=True, default=lambda self: self.env.company)
    currency_id = fields.Many2one(
        "res.currency", required=True, default=lambda self: self.env.company.currency_id, tracking=True)
    user_id = fields.Many2one(
        "res.users", string="Contract manager", default=lambda self: self.env.user, tracking=True)
    project_id = fields.Many2one("project.project", string="Project", check_company=True, tracking=True)
    analytic_account_id = fields.Many2one(
        "account.analytic.account", string="Analytic account", check_company=True, copy=False, tracking=True)
    client_reference = fields.Char(string="Client / tender reference", tracking=True)

    # ------------------------------------------------------------------
    # Dates & status
    # ------------------------------------------------------------------
    date_signed = fields.Date(string="Signing date", default=fields.Date.context_today, tracking=True)
    date_start = fields.Date(string="Start date", tracking=True)
    date_end = fields.Date(string="Planned completion", tracking=True)
    date_handover = fields.Date(string="Handover date", copy=False, tracking=True)
    dlp_months = fields.Integer(
        string="Defects liability period (months)",
        default=lambda self: self.env.company.dvz_dlp_months)
    date_dlp_end = fields.Date(
        string="Defects period ends", compute="_compute_date_dlp_end", store=True)
    state = fields.Selection(
        [
            ("draft", "Draft"),
            ("running", "In progress"),
            ("handover", "Handed over"),
            ("closed", "Closed"),
            ("cancel", "Cancelled"),
        ],
        default="draft", required=True, copy=False, tracking=True, index=True)
    boq_locked = fields.Boolean(compute="_compute_boq_locked")

    # ------------------------------------------------------------------
    # Commercial terms (used by the paid billing modules)
    # ------------------------------------------------------------------
    retention_percent = fields.Float(
        string="Retention (%)", tracking=True,
        default=lambda self: self.env.company.dvz_retention_percent)
    advance_percent = fields.Float(
        string="Advance payment (%)", tracking=True,
        default=lambda self: self.env.company.dvz_advance_percent)
    advance_amount = fields.Monetary(
        string="Advance payment", compute="_compute_advance_amount", store=True,
        readonly=False, tracking=True)
    advance_recovery_percent = fields.Float(
        string="Advance recovery per certificate (%)",
        default=lambda self: self.env.company.dvz_advance_recovery_percent)
    tax_ids = fields.Many2many(
        "account.tax", string="Taxes", check_company=True,
        default=lambda self: self._default_tax_ids())
    payment_terms_note = fields.Text(string="Payment terms")
    note = fields.Html(string="Scope & notes")

    # ------------------------------------------------------------------
    # BOQ & values
    # ------------------------------------------------------------------
    line_ids = fields.One2many("dvz.contract.line", "contract_id", string="Bill of quantities", copy=True)
    line_count = fields.Integer(compute="_compute_line_count")
    amount_original = fields.Monetary(string="Original value", compute="_compute_amounts", store=True)
    amount_variation = fields.Monetary(string="Variations", compute="_compute_amounts", store=True)
    amount_total = fields.Monetary(string="Contract value", compute="_compute_amounts", store=True, tracking=True)
    cost_budget = fields.Monetary(string="Cost budget", compute="_compute_amounts", store=True)
    margin_planned = fields.Monetary(string="Planned margin", compute="_compute_amounts", store=True)
    margin_planned_percent = fields.Float(string="Planned margin (%)", compute="_compute_amounts", store=True)

    # ------------------------------------------------------------------
    # Cost control (live, not stored)
    # ------------------------------------------------------------------
    cost_committed = fields.Monetary(
        string="Committed (open purchases)", compute="_compute_cost_control",
        help="Confirmed purchase order amounts not yet billed, for this contract's analytic account.")
    cost_actual = fields.Monetary(string="Actual cost", compute="_compute_cost_control")
    revenue_actual = fields.Monetary(string="Actual revenue", compute="_compute_cost_control")
    cost_forecast = fields.Monetary(
        string="Forecast cost", compute="_compute_cost_control",
        help="Actual cost + committed cost.")
    budget_consumed_percent = fields.Float(string="Budget used (%)", compute="_compute_cost_control")

    # ------------------------------------------------------------------
    # Defaults
    # ------------------------------------------------------------------
    @api.model
    def _default_tax_ids(self):
        company = self.env.company
        contract_type = self.env.context.get("default_contract_type", "customer")
        tax = company.dvz_purchase_tax_id if contract_type == "subcontract" else company.dvz_sale_tax_id
        return tax.ids

    # ------------------------------------------------------------------
    # Computes
    # ------------------------------------------------------------------
    @api.depends("date_handover", "dlp_months")
    def _compute_date_dlp_end(self):
        for contract in self:
            if contract.date_handover and contract.dlp_months:
                contract.date_dlp_end = contract.date_handover + relativedelta(months=contract.dlp_months)
            else:
                contract.date_dlp_end = contract.date_handover

    @api.depends("state", "company_id.dvz_lock_boq")
    def _compute_boq_locked(self):
        for contract in self:
            contract.boq_locked = contract.state != "draft" and contract.company_id.dvz_lock_boq

    @api.depends("line_ids")
    def _compute_line_count(self):
        for contract in self:
            contract.line_count = len(contract.line_ids.filtered(lambda l: not l.display_type))

    @api.depends("line_ids.amount", "line_ids.cost_amount", "line_ids.origin", "line_ids.display_type")
    def _compute_amounts(self):
        for contract in self:
            lines = contract.line_ids.filtered(lambda l: not l.display_type)
            original = sum(lines.filtered(lambda l: l.origin == "original").mapped("amount"))
            variation = sum(lines.filtered(lambda l: l.origin == "variation").mapped("amount"))
            total = original + variation
            cost = sum(lines.mapped("cost_amount"))
            contract.amount_original = original
            contract.amount_variation = variation
            contract.amount_total = total
            contract.cost_budget = cost
            contract.margin_planned = total - cost if cost else 0.0
            contract.margin_planned_percent = ((total - cost) / total * 100.0) if (cost and total) else 0.0

    @api.depends("amount_total", "advance_percent")
    def _compute_advance_amount(self):
        for contract in self:
            contract.advance_amount = contract.currency_id.round(
                contract.amount_total * contract.advance_percent / 100.0)

    def _compute_cost_control(self):
        has_purchase = "purchase.order.line" in self.env
        for contract in self:
            analytic = contract.analytic_account_id
            committed = actual = revenue = 0.0
            if analytic:
                # debit = costs, credit = revenue on the analytic account
                actual = analytic.debit
                revenue = analytic.credit
                if has_purchase:
                    committed = contract._get_committed_purchase_amount()
            contract.cost_actual = actual
            contract.revenue_actual = revenue
            contract.cost_committed = committed
            contract.cost_forecast = actual + committed
            contract.budget_consumed_percent = (
                (actual + committed) / contract.cost_budget * 100.0 if contract.cost_budget else 0.0)

    def _get_committed_purchase_amount(self):
        """Open (not yet billed) purchase amount distributed to this contract's analytic account."""
        self.ensure_one()
        analytic_id = self.analytic_account_id.id
        pol_model = self.env["purchase.order.line"]
        lines = pol_model.search([
            ("order_id.state", "in", ("purchase", "done")),
            ("analytic_distribution", "in", [analytic_id]),
            ("company_id", "=", self.company_id.id),
        ])
        total = 0.0
        for line in lines:
            share = 0.0
            for key, percent in (line.analytic_distribution or {}).items():
                if str(analytic_id) in str(key).split(","):
                    share += percent
            open_qty = max(line.product_qty - line.qty_invoiced, 0.0)
            amount = open_qty * line.price_unit * share / 100.0
            if line.currency_id and line.currency_id != self.currency_id:
                amount = line.currency_id._convert(
                    amount, self.currency_id, self.company_id, fields.Date.context_today(self))
            total += amount
        return total

    # ------------------------------------------------------------------
    # Constraints
    # ------------------------------------------------------------------
    @api.constrains("retention_percent", "advance_percent", "advance_recovery_percent")
    def _check_percentages(self):
        for contract in self:
            for value in (contract.retention_percent, contract.advance_percent, contract.advance_recovery_percent):
                if value < 0 or value > 100:
                    raise ValidationError(_("Percentages on a contract must be between 0 and 100."))

    @api.constrains("date_start", "date_end")
    def _check_dates(self):
        for contract in self:
            if contract.date_start and contract.date_end and contract.date_end < contract.date_start:
                raise ValidationError(_("Planned completion cannot be before the start date."))

    # ------------------------------------------------------------------
    # ORM
    # ------------------------------------------------------------------
    @api.model_create_multi
    def create(self, vals_list):
        for vals in vals_list:
            if not vals.get("name") or vals.get("name") == _("New"):
                code = "dvz.contract.sub" if vals.get("contract_type") == "subcontract" else "dvz.contract"
                company = self.env["res.company"].browse(vals.get("company_id")) or self.env.company
                vals["name"] = self.env["ir.sequence"].with_company(company).next_by_code(code) or _("New")
        return super().create(vals_list)

    def unlink(self):
        if any(contract.state not in ("draft", "cancel") for contract in self):
            raise UserError(_("Only draft or cancelled contracts can be deleted."))
        return super().unlink()

    @api.depends("name", "title")
    def _compute_display_name(self):
        for contract in self:
            contract.display_name = f"{contract.name} - {contract.title}" if contract.title else contract.name

    @api.onchange("contract_type")
    def _onchange_contract_type(self):
        company = self.company_id or self.env.company
        tax = company.dvz_purchase_tax_id if self.contract_type == "subcontract" else company.dvz_sale_tax_id
        self.tax_ids = tax

    @api.onchange("project_id")
    def _onchange_project_id(self):
        if self.project_id and not self.analytic_account_id and self.project_id.account_id:
            self.analytic_account_id = self.project_id.account_id

    # ------------------------------------------------------------------
    # Actions
    # ------------------------------------------------------------------
    def _get_analytic_plan(self):
        self.ensure_one()
        plan = self.company_id.dvz_analytic_plan_id
        if not plan:
            plan_id = int(self.env["ir.config_parameter"].sudo().get_param("analytic.project_plan", 0) or 0)
            plan = self.env["account.analytic.plan"].browse(plan_id).exists()
        if not plan:
            plan = self.env["account.analytic.plan"].search([], limit=1)
        return plan

    def _ensure_analytic_account(self):
        for contract in self:
            if contract.analytic_account_id or not contract.company_id.dvz_auto_analytic:
                continue
            if contract.project_id.account_id:
                contract.analytic_account_id = contract.project_id.account_id
                continue
            plan = contract._get_analytic_plan()
            if not plan:
                continue
            contract.analytic_account_id = self.env["account.analytic.account"].create({
                "name": f"{contract.name} - {contract.title}",
                "code": contract.name,
                "plan_id": plan.id,
                "partner_id": contract.partner_id.id,
                "company_id": contract.company_id.id,
            })

    def action_confirm(self):
        for contract in self:
            if contract.state != "draft":
                continue
            if not contract.line_ids.filtered(lambda l: not l.display_type):
                raise UserError(_("Add at least one BOQ line before confirming the contract."))
        self._ensure_analytic_account()
        self.filtered(lambda c: c.state == "draft").write({"state": "running"})
        return True

    def action_handover(self):
        for contract in self:
            if contract.state != "running":
                raise UserError(_("Only contracts in progress can be handed over."))
            vals = {"state": "handover"}
            if not contract.date_handover:
                vals["date_handover"] = fields.Date.context_today(contract)
            contract.write(vals)
        self._on_handover()
        return True

    def _on_handover(self):
        """Hook for extension modules (e.g. retention release)."""
        return True

    def action_close(self):
        self.write({"state": "closed"})
        return True

    def action_cancel(self):
        self._check_can_cancel()
        self.write({"state": "cancel"})
        return True

    def _check_can_cancel(self):
        """Hook: extension modules block cancellation when documents exist."""
        return True

    def action_draft(self):
        self.filtered(lambda c: c.state == "cancel").write({"state": "draft"})
        return True

    def action_view_analytic_lines(self):
        self.ensure_one()
        action = self.env["ir.actions.actions"]._for_xml_id("analytic.account_analytic_line_action_entries")
        action["domain"] = [("account_id", "=", self.analytic_account_id.id)]
        action["context"] = {"default_account_id": self.analytic_account_id.id}
        return action

    def action_view_boq_lines(self):
        self.ensure_one()
        action = self.env["ir.actions.actions"]._for_xml_id("dvz_contract.action_dvz_contract_line")
        action["domain"] = [("contract_id", "=", self.id)]
        action["context"] = {"default_contract_id": self.id}
        return action
