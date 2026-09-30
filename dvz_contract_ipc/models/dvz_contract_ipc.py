from odoo import _, api, fields, models
from odoo.exceptions import UserError, ValidationError
from odoo.tools import float_compare, float_is_zero


class DvzContractIpc(models.Model):
    _name = "dvz.contract.ipc"
    _description = "Interim payment certificate"
    _inherit = ["mail.thread", "mail.activity.mixin"]
    _order = "contract_id, sequence_number desc, id desc"
    _check_company_auto = True

    name = fields.Char(string="Number", readonly=True, copy=False, default=lambda self: _("New"))
    contract_id = fields.Many2one(
        "dvz.contract", string="Contract", required=True, index=True, tracking=True, check_company=True,
        domain="[('state', '=', 'running')]")
    contract_type = fields.Selection(related="contract_id.contract_type", store=True)
    partner_id = fields.Many2one(related="contract_id.partner_id", store=True, string="Partner")
    project_id = fields.Many2one(related="contract_id.project_id", store=True)
    company_id = fields.Many2one(related="contract_id.company_id", store=True, index=True)
    currency_id = fields.Many2one(related="contract_id.currency_id", store=True)
    sequence_number = fields.Integer(string="Certificate no.", readonly=True, copy=False)
    date = fields.Date(string="Certificate date", default=fields.Date.context_today, required=True, tracking=True)
    period_start = fields.Date(string="Period from")
    period_end = fields.Date(string="Period to")
    state = fields.Selection(
        [
            ("draft", "Draft"),
            ("submitted", "Submitted"),
            ("approved", "Approved"),
            ("invoiced", "Invoiced"),
            ("cancel", "Cancelled"),
        ],
        default="draft", required=True, copy=False, tracking=True, index=True)
    entry_mode = fields.Selection(
        [("qty", "Quantity done this period"), ("percent", "Cumulative % complete")],
        string="Progress entry", required=True,
        default=lambda self: self.env.company.dvz_ipc_entry_mode)
    line_ids = fields.One2many("dvz.contract.ipc.line", "ipc_id", string="Progress lines", copy=False)
    note = fields.Html(string="Notes")
    approved_by_id = fields.Many2one("res.users", string="Approved by", readonly=True, copy=False)
    approved_date = fields.Datetime(string="Approved on", readonly=True, copy=False)

    # ------------------------------------------------------------------
    # Amounts
    # ------------------------------------------------------------------
    amount_contract = fields.Monetary(related="contract_id.amount_total", string="Contract value")
    amount_cumulative = fields.Monetary(
        string="Cumulative work done", compute="_compute_amounts", store=True)
    amount_previous = fields.Monetary(string="Previously certified", compute="_compute_amounts", store=True)
    amount_gross = fields.Monetary(string="Work done this period", compute="_compute_amounts", store=True,
                                   tracking=True)
    progress_percent = fields.Float(string="Overall progress (%)", compute="_compute_amounts", store=True)
    retention_percent = fields.Float(
        string="Retention (%)", compute="_compute_retention_percent", store=True, readonly=False)
    retention_method = fields.Selection(
        [("deduct_line", "Deducted on invoice"), ("track_only", "Tracked only")],
        required=True, default=lambda self: self.env.company.dvz_retention_method)
    amount_retention = fields.Monetary(string="Retention", compute="_compute_deductions", store=True)
    amount_advance_recovery = fields.Monetary(
        string="Advance recovery", compute="_compute_deductions", store=True, readonly=False,
        help="Proposed from the contract's recovery % and capped at the advance still to recover. You can edit it.")
    amount_other_deduction = fields.Monetary(string="Other deductions", tracking=True)
    other_deduction_note = fields.Char(string="Deduction reason")
    amount_net = fields.Monetary(string="Net amount (excl. tax)", compute="_compute_totals", store=True)
    amount_tax = fields.Monetary(string="Tax (estimate)", compute="_compute_totals", store=True)
    amount_payable = fields.Monetary(string="Amount due", compute="_compute_totals", store=True)
    invoice_id = fields.Many2one("account.move", string="Invoice", readonly=True, copy=False)
    payment_state = fields.Selection(related="invoice_id.payment_state", string="Payment status")

    # ------------------------------------------------------------------
    # Computes
    # ------------------------------------------------------------------
    @api.depends("line_ids.amount_cumulative", "line_ids.amount_previous", "line_ids.amount_current",
                 "contract_id.amount_total")
    def _compute_amounts(self):
        for ipc in self:
            items = ipc.line_ids.filtered(lambda l: not l.display_type)
            ipc.amount_cumulative = sum(items.mapped("amount_cumulative"))
            ipc.amount_previous = sum(items.mapped("amount_previous"))
            ipc.amount_gross = sum(items.mapped("amount_current"))
            total = ipc.contract_id.amount_total
            ipc.progress_percent = ipc.amount_cumulative / total * 100.0 if total else 0.0

    @api.depends("contract_id")
    def _compute_retention_percent(self):
        for ipc in self:
            ipc.retention_percent = ipc.contract_id.retention_percent

    @api.depends("amount_gross", "retention_percent", "contract_id.advance_recovery_percent",
                 "contract_id.advance_amount")
    def _compute_deductions(self):
        for ipc in self:
            cur = ipc.currency_id or ipc.env.company.currency_id
            ipc.amount_retention = cur.round(ipc.amount_gross * ipc.retention_percent / 100.0)
            contract = ipc.contract_id
            recovered_elsewhere = sum(contract.ipc_ids.filtered(
                lambda i: i.state in ("approved", "invoiced") and i.id != ipc._origin.id
            ).mapped("amount_advance_recovery"))
            remaining = max(contract.advance_amount - recovered_elsewhere, 0.0)
            proposed = cur.round(ipc.amount_gross * contract.advance_recovery_percent / 100.0)
            ipc.amount_advance_recovery = min(proposed, remaining) if ipc.amount_gross > 0 else 0.0

    @api.depends("amount_gross", "amount_retention", "amount_advance_recovery", "amount_other_deduction",
                 "retention_method", "contract_id.tax_ids")
    def _compute_totals(self):
        for ipc in self:
            retention = ipc.amount_retention if ipc.retention_method == "deduct_line" else 0.0
            net = ipc.amount_gross - retention - ipc.amount_advance_recovery - ipc.amount_other_deduction
            taxable = ipc.amount_gross
            if ipc.company_id.dvz_advance_recovery_taxed:
                taxable -= ipc.amount_advance_recovery
            tax = 0.0
            taxes = ipc.contract_id.tax_ids
            if taxes and taxable:
                res = taxes.compute_all(taxable, currency=ipc.currency_id, quantity=1.0, partner=ipc.partner_id)
                tax = res["total_included"] - res["total_excluded"]
            ipc.amount_net = net
            ipc.amount_tax = tax
            ipc.amount_payable = net + tax

    @api.depends("name", "contract_id")
    def _compute_display_name(self):
        for ipc in self:
            ipc.display_name = ipc.name or _("New")

    # ------------------------------------------------------------------
    # Constraints & ORM
    # ------------------------------------------------------------------
    @api.constrains("contract_id", "state")
    def _check_single_open(self):
        for ipc in self:
            open_ipcs = ipc.contract_id.ipc_ids.filtered(lambda i: i.state in ("draft", "submitted"))
            if len(open_ipcs) > 1:
                raise ValidationError(_(
                    "Contract %s already has an open certificate. Approve or cancel it before starting a new one.",
                    ipc.contract_id.display_name))

    @api.constrains("retention_percent", "amount_other_deduction")
    def _check_values(self):
        for ipc in self:
            if not 0 <= ipc.retention_percent <= 100:
                raise ValidationError(_("Retention must be between 0 and 100%."))
            if ipc.amount_other_deduction < 0:
                raise ValidationError(_("Other deductions cannot be negative."))

    @api.model_create_multi
    def create(self, vals_list):
        ipcs = super().create(vals_list)
        for ipc in ipcs:
            contract = ipc.contract_id
            if contract.state != "running":
                raise UserError(_("Payment certificates can only be created for contracts in progress."))
            number = max((contract.ipc_ids - ipc).mapped("sequence_number") or [0]) + 1
            ipc.write({
                "sequence_number": number,
                "name": f"{contract.name}/IPC-{number:02d}",
                "entry_mode": ipc.entry_mode or contract.company_id.dvz_ipc_entry_mode,
                "retention_method": contract.company_id.dvz_retention_method,
            })
            if not ipc.line_ids:
                ipc._load_boq_lines()
        return ipcs

    def unlink(self):
        if any(ipc.state not in ("draft", "cancel") for ipc in self):
            raise UserError(_("Only draft or cancelled certificates can be deleted."))
        return super().unlink()

    # ------------------------------------------------------------------
    # BOQ loading
    # ------------------------------------------------------------------
    def _previous_quantities(self):
        """Quantities certified on earlier approved / invoiced certificates, by BOQ line."""
        self.ensure_one()
        previous = {}
        earlier = self.contract_id.ipc_ids.filtered(
            lambda i: i.state in ("approved", "invoiced") and i.sequence_number < self.sequence_number)
        for line in earlier.mapped("line_ids"):
            if line.contract_line_id:
                previous[line.contract_line_id.id] = previous.get(line.contract_line_id.id, 0.0) + line.current_qty
        return previous

    def _load_boq_lines(self):
        for ipc in self:
            previous = ipc._previous_quantities()
            existing = {l.contract_line_id.id: l for l in ipc.line_ids if l.contract_line_id}
            commands = []
            for boq in ipc.contract_id.line_ids:
                if boq.id in existing:
                    continue
                commands.append((0, 0, {
                    "contract_line_id": boq.id,
                    "sequence": boq.sequence,
                    "display_type": boq.display_type,
                    "name": boq.name,
                    "previous_qty": previous.get(boq.id, 0.0),
                }))
            if commands:
                ipc.write({"line_ids": commands})

    def action_refresh_lines(self):
        """Add BOQ lines created after this certificate (e.g. applied variations) and refresh previous quantities."""
        for ipc in self:
            if ipc.state != "draft":
                raise UserError(_("Only draft certificates can be refreshed."))
            ipc._load_boq_lines()
            ipc._refresh_previous()
        return True

    def _refresh_previous(self):
        for ipc in self:
            previous = ipc._previous_quantities()
            for line in ipc.line_ids.filtered("contract_line_id"):
                qty = previous.get(line.contract_line_id.id, 0.0)
                if float_compare(qty, line.previous_qty, precision_digits=3):
                    line.previous_qty = qty

    # ------------------------------------------------------------------
    # Workflow
    # ------------------------------------------------------------------
    def _check_quantities(self):
        for ipc in self:
            if float_is_zero(ipc.amount_gross, precision_rounding=ipc.currency_id.rounding or 0.01):
                raise UserError(_("Certificate %s has no progress this period.", ipc.name))
            if ipc.company_id.dvz_ipc_allow_overrun:
                continue
            over = ipc.line_ids.filtered(
                lambda l: not l.display_type and float_compare(l.cumulative_qty, l.contract_qty, precision_digits=3) > 0)
            if over:
                raise UserError(_(
                    "Cumulative quantity is above the BOQ quantity for: %s.\n"
                    "Raise a variation order or allow overruns in Settings.",
                    ", ".join(over.mapped("display_name"))))

    def action_submit(self):
        for ipc in self.filtered(lambda i: i.state == "draft"):
            ipc._refresh_previous()
            ipc._check_quantities()
            if ipc.company_id.dvz_ipc_approval_required:
                ipc.state = "submitted"
            else:
                ipc._do_approve()
        return True

    def action_approve(self):
        if not self.env.user.has_group("dvz_contract.group_contract_manager"):
            raise UserError(_("Only contracting managers can approve payment certificates."))
        for ipc in self.filtered(lambda i: i.state == "submitted"):
            ipc._check_quantities()
            ipc._do_approve()
        return True

    def _do_approve(self):
        self.write({
            "state": "approved",
            "approved_by_id": self.env.user.id,
            "approved_date": fields.Datetime.now(),
        })

    def action_reject(self):
        self.filtered(lambda i: i.state == "submitted").write({"state": "draft"})
        return True

    def action_cancel(self):
        for ipc in self:
            later = ipc.contract_id.ipc_ids.filtered(
                lambda i: i.sequence_number > ipc.sequence_number and i.state != "cancel")
            if later:
                raise UserError(_("Cancel the later certificates (%s) first.", ", ".join(later.mapped("name"))))
            if ipc.invoice_id and ipc.invoice_id.state == "posted":
                raise UserError(_("Reverse or cancel invoice %s first.", ipc.invoice_id.name))
            if ipc.invoice_id and ipc.invoice_id.state == "draft":
                ipc.invoice_id.button_cancel()
        self.write({"state": "cancel"})
        return True

    def action_draft(self):
        self.filtered(lambda i: i.state in ("cancel", "submitted")).write({"state": "draft"})
        return True

    # ------------------------------------------------------------------
    # Invoicing
    # ------------------------------------------------------------------
    def _prepare_invoice_lines(self, acc):
        self.ensure_one()
        contract = self.contract_id
        analytic = {str(contract.analytic_account_id.id): 100.0} if contract.analytic_account_id else False
        taxes = [(6, 0, contract.tax_ids.ids)]
        product = acc["product"]
        lines = []

        def base_vals(name, qty, price):
            vals = {"name": name, "quantity": qty, "price_unit": price, "tax_ids": taxes}
            if product:
                vals["product_id"] = product.id
            if acc["progress_account"]:
                vals["account_id"] = acc["progress_account"].id
            if analytic:
                vals["analytic_distribution"] = analytic
            return vals

        if self.company_id.dvz_ipc_invoice_detail == "detailed":
            for line in self.line_ids.filtered(lambda l: not l.display_type and l.current_qty):
                label = f"[{line.code}] {line.name}" if line.code else line.name
                vals = base_vals(label, line.current_qty, line.price_unit)
                if line.uom_id and not product:
                    vals["product_uom_id"] = line.uom_id.id
                lines.append(vals)
        else:
            period = ""
            if self.period_start and self.period_end:
                period = f" ({self.period_start} - {self.period_end})"
            lines.append(base_vals(
                _("Work done - %(ipc)s - %(title)s%(period)s", ipc=self.name, title=contract.title, period=period),
                1.0, self.amount_gross))

        if self.retention_method == "deduct_line" and self.amount_retention:
            if not acc["retention_account"]:
                raise UserError(_("Set the retention account in Settings > Contracting."))
            lines.append({
                "name": _("Retention %(pct)s%%", pct=self.retention_percent),
                "quantity": 1.0,
                "price_unit": -self.amount_retention,
                "account_id": acc["retention_account"].id,
                "tax_ids": [(6, 0, [])],
            })
        if self.amount_advance_recovery:
            if not acc["advance_account"]:
                raise UserError(_("Set the advance account in Settings > Contracting."))
            lines.append({
                "name": _("Advance payment recovery"),
                "quantity": 1.0,
                "price_unit": -self.amount_advance_recovery,
                "account_id": acc["advance_account"].id,
                "tax_ids": taxes if self.company_id.dvz_advance_recovery_taxed else [(6, 0, [])],
            })
        if self.amount_other_deduction:
            if not acc["deduction_account"]:
                raise UserError(_("Set the other deductions account in Settings > Contracting."))
            lines.append({
                "name": self.other_deduction_note or _("Other deductions"),
                "quantity": 1.0,
                "price_unit": -self.amount_other_deduction,
                "account_id": acc["deduction_account"].id,
                "tax_ids": [(6, 0, [])],
            })
        return lines

    def _prepare_invoice(self, acc):
        self.ensure_one()
        contract = self.contract_id
        return {
            "move_type": acc["move_type"],
            "partner_id": contract.partner_id.id,
            "journal_id": acc["journal"].id if acc["journal"] else False,
            "currency_id": contract.currency_id.id,
            "invoice_date": self.date,
            "invoice_origin": contract.name,
            "ref": self.name,
            "dvz_ipc_id": self.id,
            "dvz_contract_id": contract.id,
            "invoice_line_ids": [(0, 0, vals) for vals in self._prepare_invoice_lines(acc)],
        }

    def action_create_invoice(self):
        moves = self.env["account.move"]
        for ipc in self:
            if ipc.state != "approved":
                raise UserError(_("Only approved certificates can be invoiced."))
            acc = ipc.contract_id._get_dvz_accounts()
            vals = ipc._prepare_invoice(acc)
            if not vals["journal_id"]:
                vals.pop("journal_id")
            move = self.env["account.move"].with_company(ipc.company_id).create(vals)
            ipc.write({"invoice_id": move.id, "state": "invoiced"})
            if ipc.company_id.dvz_ipc_auto_post:
                move.action_post()
            ipc._after_invoice_created(move)
            moves |= move
        if len(moves) == 1:
            return {"type": "ir.actions.act_window", "res_model": "account.move",
                    "res_id": moves.id, "view_mode": "form"}
        return {"type": "ir.actions.act_window", "res_model": "account.move",
                "view_mode": "list,form", "domain": [("id", "in", moves.ids)]}

    def _after_invoice_created(self, move):
        """Hook for extensions."""
        return True

    def action_view_invoice(self):
        self.ensure_one()
        return {"type": "ir.actions.act_window", "res_model": "account.move",
                "res_id": self.invoice_id.id, "view_mode": "form"}
