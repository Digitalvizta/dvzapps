from odoo import api, fields, models


class DvContractLine(models.Model):
    _name = "dvz.contract.line"
    _description = "Bill of quantities line"
    _order = "contract_id, sequence, id"
    _check_company_auto = True

    contract_id = fields.Many2one("dvz.contract", required=True, ondelete="cascade", index=True)
    sequence = fields.Integer(default=10)
    display_type = fields.Selection(
        [("line_section", "Section"), ("line_note", "Note")], default=False)
    code = fields.Char(string="Item no.")
    name = fields.Text(string="Description", required=True)
    product_id = fields.Many2one("product.product", string="Product", check_company=True)
    uom_id = fields.Many2one(
        "uom.uom", string="Unit",
        default=lambda self: self.env.ref("uom.product_uom_unit", raise_if_not_found=False))
    quantity = fields.Float(string="Quantity", digits=(16, 3), default=1.0)
    price_unit = fields.Float(string="Rate", digits="Product Price")
    amount = fields.Monetary(string="Amount", compute="_compute_amounts", store=True)
    cost_price = fields.Float(string="Estimated unit cost", digits="Product Price")
    cost_amount = fields.Monetary(string="Estimated cost", compute="_compute_amounts", store=True)
    origin = fields.Selection(
        [("original", "Original"), ("variation", "Variation")],
        default="original", required=True)
    currency_id = fields.Many2one(related="contract_id.currency_id", store=True)
    company_id = fields.Many2one(related="contract_id.company_id", store=True, index=True)
    partner_id = fields.Many2one(related="contract_id.partner_id", store=True)
    contract_state = fields.Selection(related="contract_id.state", string="Contract status")

    @api.depends("quantity", "price_unit", "cost_price", "display_type")
    def _compute_amounts(self):
        for line in self:
            if line.display_type:
                line.amount = 0.0
                line.cost_amount = 0.0
            else:
                line.amount = line.currency_id.round(line.quantity * line.price_unit) if line.currency_id else line.quantity * line.price_unit
                line.cost_amount = line.quantity * line.cost_price

    @api.onchange("product_id")
    def _onchange_product_id(self):
        if self.product_id:
            self.name = self.product_id.display_name
            if self.product_id.uom_id:
                self.uom_id = self.product_id.uom_id
            if not self.price_unit:
                self.price_unit = self.product_id.lst_price
            if not self.cost_price:
                self.cost_price = self.product_id.standard_price

    @api.depends("code", "name")
    def _compute_display_name(self):
        for line in self:
            label = (line.name or "").split("\n")[0]
            line.display_name = f"[{line.code}] {label}" if line.code else label
