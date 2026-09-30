from odoo import api, fields, models


class DvzContractIpcLine(models.Model):
    _name = "dvz.contract.ipc.line"
    _description = "Payment certificate line"
    _order = "ipc_id, sequence, id"

    ipc_id = fields.Many2one("dvz.contract.ipc", required=True, ondelete="cascade", index=True)
    contract_line_id = fields.Many2one("dvz.contract.line", string="BOQ item", ondelete="restrict")
    sequence = fields.Integer(default=10)
    display_type = fields.Selection([("line_section", "Section"), ("line_note", "Note")], default=False)
    name = fields.Text(string="Description", required=True)
    code = fields.Char(related="contract_line_id.code", string="Item no.")
    uom_id = fields.Many2one(related="contract_line_id.uom_id", string="Unit")
    contract_qty = fields.Float(related="contract_line_id.quantity", string="BOQ qty", digits=(16, 3))
    price_unit = fields.Float(related="contract_line_id.price_unit", string="Rate")
    currency_id = fields.Many2one(related="ipc_id.currency_id", store=True)
    company_id = fields.Many2one(related="ipc_id.company_id", store=True)
    entry_mode = fields.Selection(related="ipc_id.entry_mode")
    ipc_state = fields.Selection(related="ipc_id.state")

    previous_qty = fields.Float(string="Previous qty", digits=(16, 3), readonly=True)
    current_qty = fields.Float(string="This period qty", digits=(16, 3))
    cumulative_qty = fields.Float(string="Cumulative qty", digits=(16, 3),
                                  compute="_compute_cumulative", store=True)
    cumulative_percent = fields.Float(
        string="Cumulative %", digits=(16, 2), compute="_compute_cumulative",
        inverse="_inverse_cumulative_percent", store=True)

    amount_previous = fields.Monetary(string="Previous amount", compute="_compute_line_amounts", store=True)
    amount_current = fields.Monetary(string="This period", compute="_compute_line_amounts", store=True)
    amount_cumulative = fields.Monetary(string="Cumulative amount", compute="_compute_line_amounts", store=True)

    @api.depends("previous_qty", "current_qty", "contract_qty")
    def _compute_cumulative(self):
        for line in self:
            line.cumulative_qty = line.previous_qty + line.current_qty
            line.cumulative_percent = (
                line.cumulative_qty / line.contract_qty * 100.0 if line.contract_qty else 0.0)

    def _inverse_cumulative_percent(self):
        for line in self:
            if line.display_type:
                continue
            target = line.contract_qty * line.cumulative_percent / 100.0
            line.current_qty = target - line.previous_qty

    @api.depends("previous_qty", "current_qty", "price_unit", "display_type")
    def _compute_line_amounts(self):
        for line in self:
            if line.display_type:
                line.amount_previous = line.amount_current = line.amount_cumulative = 0.0
                continue
            cur = line.currency_id
            rnd = cur.round if cur else (lambda x: round(x, 2))
            line.amount_previous = rnd(line.previous_qty * line.price_unit)
            line.amount_current = rnd(line.current_qty * line.price_unit)
            line.amount_cumulative = line.amount_previous + line.amount_current

    @api.depends("code", "name")
    def _compute_display_name(self):
        for line in self:
            label = (line.name or "").split("\n")[0]
            line.display_name = f"[{line.code}] {label}" if line.code else label
