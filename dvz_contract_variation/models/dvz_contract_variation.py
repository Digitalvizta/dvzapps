from odoo import _, api, fields, models
from odoo.exceptions import UserError, ValidationError


class DvzContractVariation(models.Model):
    _name = "dvz.contract.variation"
    _description = "Variation order"
    _inherit = ["mail.thread", "mail.activity.mixin"]
    _order = "contract_id, sequence_number desc, id desc"
    _check_company_auto = True

    name = fields.Char(string="Number", readonly=True, copy=False, default=lambda self: _("New"))
    sequence_number = fields.Integer(readonly=True, copy=False)
    title = fields.Char(required=True, tracking=True)
    contract_id = fields.Many2one("dvz.contract", required=True, index=True, tracking=True, check_company=True,
                                  domain="[('state', 'in', ('draft', 'running'))]")
    contract_type = fields.Selection(related="contract_id.contract_type", store=True)
    partner_id = fields.Many2one(related="contract_id.partner_id", store=True)
    company_id = fields.Many2one(related="contract_id.company_id", store=True, index=True)
    currency_id = fields.Many2one(related="contract_id.currency_id", store=True)
    reason = fields.Selection(
        [("client", "Client instruction"), ("design", "Design change"), ("site", "Site condition"),
         ("omission", "Omission"), ("other", "Other")], default="client", required=True, tracking=True)
    instruction_ref = fields.Char(string="Instruction ref.", tracking=True,
                                  help="Site instruction / engineer's instruction number.")
    date_instruction = fields.Date(string="Instruction date", default=fields.Date.context_today)
    date_approved = fields.Date(string="Approval date", readonly=True, copy=False)
    extension_days = fields.Integer(string="Time extension (days)", tracking=True)
    state = fields.Selection(
        [("draft", "Draft"), ("submitted", "Submitted"), ("approved", "Approved"),
         ("applied", "Applied to BOQ"), ("rejected", "Rejected"), ("cancel", "Cancelled")],
        default="draft", required=True, copy=False, tracking=True, index=True)
    line_ids = fields.One2many("dvz.contract.variation.line", "variation_id", copy=True)
    amount_total = fields.Monetary(string="Variation value", compute="_compute_amount", store=True, tracking=True)
    description = fields.Html()

    @api.depends("line_ids.amount_change")
    def _compute_amount(self):
        for vo in self:
            vo.amount_total = sum(vo.line_ids.mapped("amount_change"))

    @api.depends("name", "title")
    def _compute_display_name(self):
        for vo in self:
            vo.display_name = f"{vo.name} - {vo.title}" if vo.title else vo.name

    @api.model_create_multi
    def create(self, vals_list):
        records = super().create(vals_list)
        for vo in records:
            number = max((vo.contract_id.variation_ids - vo).mapped("sequence_number") or [0]) + 1
            vo.write({"sequence_number": number, "name": f"{vo.contract_id.name}/VO-{number:02d}"})
        return records

    def unlink(self):
        if any(vo.state not in ("draft", "cancel", "rejected") for vo in self):
            raise UserError(_("Only draft, rejected or cancelled variations can be deleted."))
        return super().unlink()

    def _check_lines(self):
        for vo in self:
            if not vo.line_ids:
                raise UserError(_("Add at least one line to %s.", vo.name))
            if vo.amount_total < 0 and not vo.company_id.dvz_vo_allow_negative:
                raise UserError(_("Omissions (negative variations) are disabled in Settings."))

    def action_submit(self):
        drafts = self.filtered(lambda v: v.state == "draft")
        drafts._check_lines()
        for vo in drafts:
            if vo.company_id.dvz_vo_approval_required:
                vo.state = "submitted"
            else:
                vo._do_approve()
        return True

    def action_approve(self):
        if not self.env.user.has_group("dvz_contract.group_contract_manager"):
            raise UserError(_("Only contracting managers can approve variations."))
        self.filtered(lambda v: v.state == "submitted")._do_approve()
        return True

    def _do_approve(self):
        self.write({"state": "approved", "date_approved": fields.Date.context_today(self)})
        self.filtered(lambda v: v.company_id.dvz_vo_auto_apply).action_apply()

    def action_reject(self):
        self.filtered(lambda v: v.state == "submitted").write({"state": "rejected"})
        return True

    def action_cancel(self):
        if any(v.state == "applied" for v in self):
            raise UserError(_("An applied variation cannot be cancelled. Create a new omission variation instead."))
        self.write({"state": "cancel"})
        return True

    def action_draft(self):
        self.filtered(lambda v: v.state in ("rejected", "cancel", "submitted")).write({"state": "draft"})
        return True

    def action_apply(self):
        Line = self.env["dvz.contract.line"]
        for vo in self.filtered(lambda v: v.state == "approved"):
            contract = vo.contract_id
            new_lines = vo.line_ids.filtered(lambda l: l.change_type == "add")
            section = False
            if new_lines:
                section = Line.create({
                    "contract_id": contract.id, "display_type": "line_section",
                    "name": vo.display_name, "origin": "variation", "variation_id": vo.id,
                    "sequence": max(contract.line_ids.mapped("sequence") or [0]) + 10,
                })
            seq = section.sequence if section else 0
            for line in vo.line_ids:
                if line.change_type == "add":
                    seq += 1
                    boq = Line.create({
                        "contract_id": contract.id,
                        "sequence": seq,
                        "code": line.code,
                        "name": line.name,
                        "product_id": line.product_id.id,
                        "uom_id": line.uom_id.id,
                        "quantity": line.quantity,
                        "price_unit": line.price_unit,
                        "cost_price": line.cost_price,
                        "origin": "variation",
                        "variation_id": vo.id,
                    })
                    line.contract_line_id = boq
                else:
                    boq = line.contract_line_id
                    # Adjustment is added as a separate variation line so the original BOQ stays auditable.
                    Line.create({
                        "contract_id": contract.id,
                        "sequence": boq.sequence,
                        "code": boq.code,
                        "name": _("%(name)s (%(vo)s adjustment)", name=boq.name, vo=vo.name),
                        "product_id": boq.product_id.id,
                        "uom_id": boq.uom_id.id,
                        "quantity": line.quantity_change,
                        "price_unit": line.price_unit,
                        "cost_price": boq.cost_price,
                        "origin": "variation",
                        "variation_id": vo.id,
                    })
            if vo.extension_days and contract.date_end:
                contract.date_end = fields.Date.add(contract.date_end, days=vo.extension_days)
            contract.message_post(body=_("Variation %(vo)s applied: %(amount)s", vo=vo.display_name,
                                         amount=vo.amount_total))
            vo.state = "applied"
        return True


class DvzContractVariationLine(models.Model):
    _name = "dvz.contract.variation.line"
    _description = "Variation order line"
    _order = "variation_id, sequence, id"

    variation_id = fields.Many2one("dvz.contract.variation", required=True, ondelete="cascade", index=True)
    contract_id = fields.Many2one(related="variation_id.contract_id")
    currency_id = fields.Many2one(related="variation_id.currency_id", store=True)
    company_id = fields.Many2one(related="variation_id.company_id", store=True)
    sequence = fields.Integer(default=10)
    change_type = fields.Selection(
        [("add", "New item"), ("adjust", "Change existing item")], required=True, default="add")
    contract_line_id = fields.Many2one(
        "dvz.contract.line", string="BOQ item",
        domain="[('contract_id', '=', contract_id), ('display_type', '=', False)]")
    code = fields.Char(string="Item no.")
    name = fields.Text(string="Description", required=True)
    product_id = fields.Many2one("product.product")
    uom_id = fields.Many2one("uom.uom", string="Unit")
    quantity_before = fields.Float(related="contract_line_id.quantity", string="Current qty")
    quantity_change = fields.Float(string="Qty change (+/-)", digits=(16, 3))
    quantity = fields.Float(string="Quantity", digits=(16, 3), default=1.0)
    price_unit = fields.Float(string="Rate", digits="Product Price")
    cost_price = fields.Float(string="Estimated unit cost", digits="Product Price")
    amount_change = fields.Monetary(string="Value", compute="_compute_amount_change", store=True)

    @api.depends("change_type", "quantity", "quantity_change", "price_unit")
    def _compute_amount_change(self):
        for line in self:
            qty = line.quantity if line.change_type == "add" else line.quantity_change
            line.amount_change = qty * line.price_unit

    @api.onchange("contract_line_id")
    def _onchange_contract_line_id(self):
        boq = self.contract_line_id
        if boq:
            self.code = boq.code
            self.name = boq.name
            self.uom_id = boq.uom_id
            self.price_unit = boq.price_unit
            self.product_id = boq.product_id

    @api.onchange("product_id")
    def _onchange_product_id(self):
        if self.product_id and self.change_type == "add":
            self.name = self.product_id.display_name
            self.uom_id = self.product_id.uom_id
            self.price_unit = self.price_unit or self.product_id.lst_price
            self.cost_price = self.cost_price or self.product_id.standard_price

    @api.constrains("change_type", "contract_line_id")
    def _check_adjust(self):
        for line in self:
            if line.change_type == "adjust" and not line.contract_line_id:
                raise ValidationError(_("Select the BOQ item to change."))
