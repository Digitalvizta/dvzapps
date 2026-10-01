from odoo import _, fields, models


class ManpowerContract(models.Model):
    _inherit = 'dvz.manpower.contract'

    invoice_count = fields.Integer(compute='_compute_invoice_stats')
    amount_invoiced = fields.Monetary(compute='_compute_invoice_stats', currency_field='currency_id')

    def _compute_invoice_stats(self):
        for contract in self:
            invoices = contract.timesheet_ids.invoice_id.filtered(lambda m: m.state != 'cancel')
            contract.invoice_count = len(invoices)
            contract.amount_invoiced = sum(invoices.mapped('amount_untaxed_signed'))

    def action_view_invoices(self):
        self.ensure_one()
        invoices = self.timesheet_ids.invoice_id
        action = self.env['ir.actions.act_window']._for_xml_id('account.action_move_out_invoice_type')
        action['domain'] = [('id', 'in', invoices.ids)]
        action['context'] = {'default_move_type': 'out_invoice', 'create': False}
        return action
