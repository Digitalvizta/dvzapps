from odoo import Command, _, fields, models
from odoo.exceptions import UserError


class RentalContract(models.Model):
    _inherit = 'dvz.rental.contract'

    invoice_count = fields.Integer(compute='_compute_invoice_stats', compute_sudo=True)
    amount_invoiced = fields.Monetary(
        compute='_compute_invoice_stats', compute_sudo=True, currency_field='currency_id')
    mobilization_invoiced = fields.Boolean(compute='_compute_invoice_stats', compute_sudo=True)
    demobilization_invoiced = fields.Boolean(compute='_compute_invoice_stats', compute_sudo=True)

    def _get_invoices(self):
        return self.env['account.move'].sudo().search([
            ('dv_rental_contract_id', 'in', self.ids), ('state', '!=', 'cancel')])

    def _compute_invoice_stats(self):
        for contract in self:
            invoices = contract._get_invoices() if contract.id else self.env['account.move']
            contract.invoice_count = len(invoices)
            contract.amount_invoiced = sum(invoices.mapped('amount_untaxed_signed'))
            contract.mobilization_invoiced = any(invoices.mapped('dv_includes_mobilization'))
            contract.demobilization_invoiced = any(invoices.mapped('dv_includes_demobilization'))

    def _create_fee_invoice(self, kind):
        """Invoice the mobilization or demobilization fee on its own."""
        self.ensure_one()
        if kind == 'mobilization':
            fee, done = self.mobilization_fee, self.mobilization_invoiced
            product = self.env.ref('dvz_equipment_rental_billing.product_equipment_mobilization')
            label = _('Mobilization to %s', self.site or self.partner_id.name)
        else:
            fee, done = self.demobilization_fee, self.demobilization_invoiced
            product = self.env.ref('dvz_equipment_rental_billing.product_equipment_demobilization')
            label = _('Demobilization from %s', self.site or self.partner_id.name)
        if not fee or done:
            raise UserError(_('There is no %s fee left to invoice on %s.', kind, self.name))
        invoice = self.env['account.move'].with_company(self.company_id).create({
            'move_type': 'out_invoice',
            'partner_id': self.partner_id.id,
            'company_id': self.company_id.id,
            'invoice_date': fields.Date.context_today(self),
            'ref': self.client_reference or self.name,
            'invoice_origin': self.name,
            'dv_rental_contract_id': self.id,
            'dv_includes_mobilization': kind == 'mobilization',
            'dv_includes_demobilization': kind == 'demobilization',
            'invoice_line_ids': [Command.create({
                'product_id': product.id, 'name': label, 'quantity': 1.0, 'price_unit': fee})],
        })
        self.message_post(body=_('Invoice %s created.', invoice._get_html_link()))
        return self.env['dvz.equipment.logsheet']._action_open_invoices(invoice)

    def action_invoice_mobilization(self):
        return self._create_fee_invoice('mobilization')

    def action_invoice_demobilization(self):
        return self._create_fee_invoice('demobilization')

    def action_view_invoices(self):
        self.ensure_one()
        action = self.env['ir.actions.act_window']._for_xml_id('account.action_move_out_invoice_type')
        action['domain'] = [('dv_rental_contract_id', '=', self.id)]
        action['context'] = {'default_move_type': 'out_invoice', 'create': False}
        return action


class RentalContractLine(models.Model):
    _inherit = 'dvz.rental.contract.line'

    min_hours = fields.Float(
        string='Minimum Hours',
        help='Hourly rentals only: minimum hours billed per log sheet (e.g. 200 hours per month). '
             'If the client used less, the difference is added to the invoice.')
