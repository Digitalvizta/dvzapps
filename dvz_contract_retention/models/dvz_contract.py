from datetime import timedelta

from odoo import _, api, fields, models
from odoo.exceptions import UserError


class DvzContract(models.Model):
    _inherit = "dvz.contract"

    retention_release_ids = fields.One2many("dvz.retention.release", "contract_id")
    guarantee_ids = fields.One2many("dvz.bank.guarantee", "contract_id")
    retention_released = fields.Monetary(compute="_compute_retention_ledger", string="Retention released")
    retention_balance = fields.Monetary(compute="_compute_retention_ledger", string="Retention balance")
    release_count = fields.Integer(compute="_compute_retention_ledger")
    guarantee_count = fields.Integer(compute="_compute_retention_ledger")

    @api.depends("retention_held", "retention_release_ids.state", "retention_release_ids.amount", "guarantee_ids")
    def _compute_retention_ledger(self):
        for contract in self:
            released = sum(contract.retention_release_ids.filtered(lambda r: r.state == "done").mapped("amount"))
            contract.retention_released = released
            contract.retention_balance = contract.retention_held - released
            contract.release_count = len(contract.retention_release_ids)
            contract.guarantee_count = len(contract.guarantee_ids)

    def _on_handover(self):
        res = super()._on_handover()
        for contract in self:
            company = contract.company_id
            if not company.dvz_release_auto_on_handover or contract.retention_balance <= 0:
                continue
            if contract.retention_release_ids.filtered(lambda r: r.stage == "handover" and r.state != "cancel"):
                continue
            self.env["dvz.retention.release"].create({
                "contract_id": contract.id,
                "stage": "handover",
                "percent": company.dvz_release_handover_percent,
            })
        return res

    def _check_can_cancel(self):
        res = super()._check_can_cancel()
        for contract in self:
            if contract.retention_release_ids.filtered(lambda r: r.state == "done"):
                raise UserError(_("Contract %s has released retention.", contract.display_name))
        return res

    def action_new_release(self):
        self.ensure_one()
        stage = "dlp" if self.state in ("handover", "closed") and self.retention_released else "handover"
        return {
            "type": "ir.actions.act_window",
            "res_model": "dvz.retention.release",
            "view_mode": "form",
            "context": {"default_contract_id": self.id, "default_stage": stage,
                        "default_percent": 100.0 if stage == "dlp" else self.company_id.dvz_release_handover_percent},
        }

    def action_view_releases(self):
        self.ensure_one()
        action = self.env["ir.actions.actions"]._for_xml_id("dvz_contract_retention.action_dvz_retention_release")
        action["domain"] = [("contract_id", "=", self.id)]
        action["context"] = {"default_contract_id": self.id}
        return action

    def action_view_guarantees(self):
        self.ensure_one()
        action = self.env["ir.actions.actions"]._for_xml_id("dvz_contract_retention.action_dvz_bank_guarantee")
        action["domain"] = [("contract_id", "=", self.id)]
        action["context"] = {"default_contract_id": self.id, "default_partner_id": self.partner_id.id,
                             "default_currency_id": self.currency_id.id}
        return action

    @api.model
    def _cron_dlp_reminders(self):
        today = fields.Date.context_today(self)
        activity_type = self.env.ref("mail.mail_activity_data_todo", raise_if_not_found=False)
        if not activity_type:
            return
        for company in self.env["res.company"].search([]):
            limit = today + timedelta(days=company.dvz_retention_reminder_days or 0)
            contracts = self.search([
                ("company_id", "=", company.id), ("state", "=", "handover"),
                ("date_dlp_end", "!=", False), ("date_dlp_end", "<=", limit),
            ])
            for contract in contracts.filtered(lambda c: c.retention_balance > 0):
                if contract.activity_ids.filtered(lambda a: a.activity_type_id == activity_type
                                                  and "retention" in (a.summary or "").lower()):
                    continue
                contract.activity_schedule(
                    activity_type_id=activity_type.id, date_deadline=contract.date_dlp_end,
                    user_id=(contract.user_id or self.env.user).id,
                    summary=_("Defects period ends: release final retention"))
