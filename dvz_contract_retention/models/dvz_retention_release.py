from odoo import _, api, fields, models
from odoo.exceptions import UserError, ValidationError


class DvzRetentionRelease(models.Model):
    _name = "dvz.retention.release"
    _description = "Retention release"
    _inherit = ["mail.thread", "mail.activity.mixin"]
    _order = "date desc, id desc"
    _check_company_auto = True

    name = fields.Char(string="Number", readonly=True, copy=False, default=lambda self: _("New"))
    contract_id = fields.Many2one("dvz.contract", required=True, index=True, tracking=True, check_company=True,
                                  domain="[('state', 'in', ('running', 'handover', 'closed'))]")
    contract_type = fields.Selection(related="contract_id.contract_type", store=True)
    partner_id = fields.Many2one(related="contract_id.partner_id", store=True)
    company_id = fields.Many2one(related="contract_id.company_id", store=True, index=True)
    currency_id = fields.Many2one(related="contract_id.currency_id", store=True)
    stage = fields.Selection(
        [("handover", "At handover"), ("dlp", "End of defects period"), ("other", "Other")],
        required=True, default="handover", tracking=True)
    date = fields.Date(default=fields.Date.context_today, required=True, tracking=True)
    retention_balance = fields.Monetary(related="contract_id.retention_balance", string="Balance before release")
    percent = fields.Float(string="Release (% of held)", tracking=True)
    amount = fields.Monetary(string="Amount released", compute="_compute_amount", store=True, readonly=False,
                             tracking=True)
    method = fields.Selection(
        [("deduct_line", "Invoice the retention receivable"), ("track_only", "Record only")],
        required=True, default=lambda self: self.env.company.dvz_retention_method,
        help="Invoice: a release invoice moves the amount from the retention account to the partner.\n"
             "Record only: use when retention was never deducted on invoices.")
    state = fields.Selection(
        [("draft", "Draft"), ("done", "Released"), ("cancel", "Cancelled")],
        default="draft", required=True, copy=False, tracking=True)
    invoice_id = fields.Many2one("account.move", readonly=True, copy=False)
    note = fields.Text()

    @api.depends("percent", "contract_id.retention_held")
    def _compute_amount(self):
        for rec in self:
            if rec.percent:
                rec.amount = rec.currency_id.round(rec.contract_id.retention_held * rec.percent / 100.0)
            else:
                rec.amount = rec.amount or 0.0

    @api.constrains("amount", "percent")
    def _check_amount(self):
        for rec in self:
            if rec.amount < 0 or not 0 <= rec.percent <= 100:
                raise ValidationError(_("Release amount and percentage must be positive (percentage up to 100)."))

    @api.model_create_multi
    def create(self, vals_list):
        for vals in vals_list:
            if not vals.get("name") or vals["name"] == _("New"):
                vals["name"] = self.env["ir.sequence"].next_by_code("dvz.retention.release") or _("New")
        return super().create(vals_list)

    def unlink(self):
        if any(r.state == "done" for r in self):
            raise UserError(_("Released retention cannot be deleted. Cancel it first."))
        return super().unlink()

    def action_release(self):
        for rec in self.filtered(lambda r: r.state == "draft"):
            if rec.amount <= 0:
                raise UserError(_("Nothing to release on %s.", rec.name))
            balance = rec.contract_id.retention_balance
            if rec.currency_id.compare_amounts(rec.amount, balance) > 0:
                raise UserError(_("You cannot release more than the retention balance (%s).", balance))
            if rec.method == "deduct_line":
                rec._create_release_invoice()
            rec.state = "done"
        return True

    def _create_release_invoice(self):
        self.ensure_one()
        contract = self.contract_id
        acc = contract._get_dvz_accounts()
        if not acc["retention_account"]:
            raise UserError(_("Set the retention account in Settings > Contracting."))
        vals = {
            "move_type": acc["move_type"],
            "partner_id": contract.partner_id.id,
            "currency_id": contract.currency_id.id,
            "invoice_date": self.date,
            "invoice_origin": contract.name,
            "ref": self.name,
            "dvz_contract_id": contract.id,
            "invoice_line_ids": [(0, 0, {
                "name": _("Retention release - %(stage)s - %(contract)s",
                          stage=dict(self._fields["stage"].selection)[self.stage], contract=contract.name),
                "quantity": 1.0,
                "price_unit": self.amount,
                "account_id": acc["retention_account"].id,
                "tax_ids": [(6, 0, [])],
            })],
        }
        if acc["journal"]:
            vals["journal_id"] = acc["journal"].id
        move = self.env["account.move"].with_company(self.company_id).create(vals)
        self.invoice_id = move
        if self.company_id.dvz_ipc_auto_post:
            move.action_post()
        return move

    def action_cancel(self):
        for rec in self:
            if rec.invoice_id and rec.invoice_id.state == "posted":
                raise UserError(_("Reverse invoice %s first.", rec.invoice_id.name))
            if rec.invoice_id:
                rec.invoice_id.button_cancel()
        self.write({"state": "cancel"})
        return True

    def action_draft(self):
        self.filtered(lambda r: r.state == "cancel").write({"state": "draft", "invoice_id": False})
        return True

    def action_view_invoice(self):
        self.ensure_one()
        return {"type": "ir.actions.act_window", "res_model": "account.move",
                "res_id": self.invoice_id.id, "view_mode": "form"}
