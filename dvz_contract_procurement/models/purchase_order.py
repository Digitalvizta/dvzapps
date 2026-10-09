from collections import defaultdict

from odoo import _, api, fields, models
from odoo.exceptions import UserError


class PurchaseOrder(models.Model):
    _inherit = 'purchase.order'

    dvz_contract_id = fields.Many2one(
        'dvz.contract', 'Contract', index='btree_not_null', tracking=True, copy=False,
        domain="[('contract_type', '=', 'client'), ('state', 'in', ('progress', 'handover')), ('company_id', '=', company_id)]")
    dvz_material_request_id = fields.Many2one('dvz.material.request', 'Material Request', copy=False, readonly=True,
                                              index='btree_not_null')

    def button_confirm(self):
        self._dvz_check_budget()
        return super().button_confirm()

    def _dvz_check_budget(self):
        is_manager = self.env.user.has_group('dvz_contract.group_dvz_contract_manager')
        for order in self:
            if order.state not in ('draft', 'sent'):
                continue
            new_amounts = defaultdict(float)
            for line in order.order_line.filtered(lambda l: l.dvz_contract_line_id and not l.display_type):
                new_amounts[line.dvz_contract_line_id] += line._dvz_amount_in_contract_currency(line.price_subtotal)
            messages = []
            for boq, amount in new_amounts.items():
                if not boq.cost_subtotal:
                    continue
                total = boq.cost_committed + amount
                if boq.currency_id.compare_amounts(total, boq.cost_subtotal) > 0:
                    messages.append(_(
                        '%(item)s %(name)s: budget %(budget)s, ordered after this PO %(total)s (over by %(over)s)',
                        item=boq.item_no or '', name=(boq.name or '')[:60],
                        budget=boq.currency_id.format(boq.cost_subtotal),
                        total=boq.currency_id.format(total),
                        over=boq.currency_id.format(total - boq.cost_subtotal)))
            if not messages:
                continue
            text = _('This purchase order takes BOQ items over their cost budget:') + '\n' + '\n'.join(messages)
            if order.company_id.dvz_block_over_budget and not is_manager:
                raise UserError(text + '\n\n' + _('Ask a contracting manager to confirm it.'))
            order.message_post(body=text)

    def action_view_dvz_contract(self):
        self.ensure_one()
        return {
            'type': 'ir.actions.act_window',
            'res_model': 'dvz.contract',
            'res_id': self.dvz_contract_id.id,
            'view_mode': 'form',
        }


class PurchaseOrderLine(models.Model):
    _inherit = 'purchase.order.line'

    dvz_contract_line_id = fields.Many2one('dvz.contract.line', 'BOQ Item', index='btree_not_null', copy=False)
    dvz_request_line_id = fields.Many2one('dvz.material.request.line', 'Material Request Line', copy=False,
                                          readonly=True, index='btree_not_null')

    @api.depends('dvz_contract_line_id', 'order_id.dvz_contract_id')
    def _compute_analytic_distribution(self):
        super()._compute_analytic_distribution()
        for line in self:
            if line.display_type:
                continue
            contract = line.dvz_contract_line_id.contract_id or line.order_id.dvz_contract_id
            if contract.analytic_account_id:
                line.analytic_distribution = {str(contract.analytic_account_id.id): 100.0}

    def _dvz_amount_in_contract_currency(self, amount):
        self.ensure_one()
        contract = self.dvz_contract_line_id.contract_id
        if not contract or not amount or self.currency_id == contract.currency_id:
            return amount
        return self.currency_id._convert(amount, contract.currency_id, contract.company_id,
                                         self.order_id.date_order or fields.Date.today())
