from datetime import timedelta

from odoo import _, api, fields, models
from odoo.exceptions import ValidationError


class DvzBankGuarantee(models.Model):
    _name = "dvz.bank.guarantee"
    _description = "Bank guarantee"
    _inherit = ["mail.thread", "mail.activity.mixin"]
    _order = "date_expiry, id"
    _check_company_auto = True

    name = fields.Char(string="Guarantee no.", required=True, tracking=True)
    guarantee_type = fields.Selection(
        [("bid", "Bid bond"), ("performance", "Performance bond"), ("advance", "Advance payment guarantee"),
         ("retention", "Retention bond"), ("other", "Other")],
        string="Type", required=True, default="performance", tracking=True)
    direction = fields.Selection(
        [("given", "Given (we issued it)"), ("received", "Received (in our favour)")],
        required=True, default="given", tracking=True)
    contract_id = fields.Many2one("dvz.contract", index=True, tracking=True, check_company=True)
    partner_id = fields.Many2one("res.partner", string="Beneficiary / applicant", required=True, tracking=True)
    bank_id = fields.Many2one("res.partner", string="Issuing bank", tracking=True)
    company_id = fields.Many2one("res.company", required=True, default=lambda self: self.env.company, index=True)
    currency_id = fields.Many2one("res.currency", required=True,
                                  default=lambda self: self.env.company.currency_id)
    amount = fields.Monetary(required=True, tracking=True)
    percent_of_contract = fields.Float(string="% of contract", compute="_compute_percent")
    date_issue = fields.Date(string="Issue date", default=fields.Date.context_today)
    date_expiry = fields.Date(string="Expiry date", required=True, tracking=True)
    days_to_expiry = fields.Integer(compute="_compute_days_to_expiry")
    commission_amount = fields.Monetary(string="Bank commission")
    state = fields.Selection(
        [("draft", "Draft"), ("active", "Active"), ("released", "Released"),
         ("expired", "Expired"), ("claimed", "Claimed")],
        default="draft", required=True, tracking=True, index=True)
    note = fields.Text()

    @api.depends("amount", "contract_id.amount_total")
    def _compute_percent(self):
        for g in self:
            total = g.contract_id.amount_total
            g.percent_of_contract = g.amount / total * 100.0 if total else 0.0

    def _compute_days_to_expiry(self):
        today = fields.Date.context_today(self)
        for g in self:
            g.days_to_expiry = (g.date_expiry - today).days if g.date_expiry else 0

    @api.onchange("contract_id")
    def _onchange_contract_id(self):
        if self.contract_id:
            self.partner_id = self.contract_id.partner_id
            self.currency_id = self.contract_id.currency_id
            self.company_id = self.contract_id.company_id

    @api.constrains("date_issue", "date_expiry", "amount")
    def _check_values(self):
        for g in self:
            if g.date_issue and g.date_expiry and g.date_expiry < g.date_issue:
                raise ValidationError(_("Expiry date cannot be before the issue date."))
            if g.amount <= 0:
                raise ValidationError(_("Guarantee amount must be positive."))

    def action_activate(self):
        self.filtered(lambda g: g.state == "draft").write({"state": "active"})

    def action_release(self):
        self.filtered(lambda g: g.state in ("active", "expired")).write({"state": "released"})

    def action_claim(self):
        self.filtered(lambda g: g.state == "active").write({"state": "claimed"})

    def action_draft(self):
        self.write({"state": "draft"})

    @api.model
    def _cron_guarantee_reminders(self):
        today = fields.Date.context_today(self)
        activity_type = self.env.ref("mail.mail_activity_data_todo", raise_if_not_found=False)
        for company in self.env["res.company"].search([]):
            active = self.search([("company_id", "=", company.id), ("state", "=", "active")])
            if company.dvz_guarantee_auto_expire:
                active.filtered(lambda g: g.date_expiry < today).write({"state": "expired"})
            limit = today + timedelta(days=company.dvz_guarantee_reminder_days or 0)
            for g in active.filtered(lambda g: g.state == "active" and today <= g.date_expiry <= limit):
                if activity_type and not g.activity_ids.filtered(lambda a: a.activity_type_id == activity_type):
                    user = g.contract_id.user_id or g.create_uid
                    g.activity_schedule(
                        activity_type_id=activity_type.id, date_deadline=g.date_expiry, user_id=user.id,
                        summary=_("Guarantee %s expires on %s: extend or release", g.name, g.date_expiry))
