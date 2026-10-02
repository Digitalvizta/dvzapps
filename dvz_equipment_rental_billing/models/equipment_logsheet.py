import calendar
from datetime import date

from odoo import Command, _, api, fields, models
from odoo.exceptions import UserError

FRIDAY = 4


def working_days_in_month(day):
    """Working days (Fridays excluded) of the calendar month of ``day``."""
    last = calendar.monthrange(day.year, day.month)[1]
    return sum(1 for d in range(1, last + 1) if date(day.year, day.month, d).weekday() != FRIDAY) or 26


class EquipmentLogsheet(models.Model):
    _inherit = 'dvz.equipment.logsheet'

    currency_id = fields.Many2one(related='contract_id.currency_id')
    amount_total = fields.Monetary(
        string='Amount (excl. VAT)', compute='_compute_amount_total', store=True, currency_field='currency_id')
    invoice_id = fields.Many2one('account.move', string='Invoice', readonly=True, copy=False, tracking=True)
    invoice_state = fields.Selection(related='invoice_id.state', string='Invoice Status')
    invoice_payment_state = fields.Selection(related='invoice_id.payment_state', string='Payment Status')

    @api.depends('line_ids.amount_regular', 'line_ids.amount_extra', 'line_ids.working_hours',
                 'line_ids.contract_line_id.min_hours', 'line_ids.contract_line_id.rate')
    def _compute_amount_total(self):
        # Rounded per machine and per kind (rental / extra hours) exactly like the invoice lines
        for sheet in self:
            currency = sheet.currency_id or sheet.env.company.currency_id
            total = 0.0
            for rental_line in sheet.line_ids.contract_line_id:
                logs = sheet.line_ids.filtered(lambda l: l.contract_line_id == rental_line)
                total += currency.round(sum(logs.mapped('amount_regular')))
                total += currency.round(sum(logs.mapped('amount_extra')))
                total += currency.round(sheet._get_min_hours_topup(rental_line, logs) * rental_line.rate)
            sheet.amount_total = total

    @api.model
    def _get_min_hours_topup(self, rental_line, logs):
        """Hours to add on hourly rentals that used less than the guaranteed minimum."""
        if rental_line.rate_type != 'hour' or not rental_line.min_hours:
            return 0.0
        return max(rental_line.min_hours - sum(logs.mapped('working_hours')), 0.0)

    def _prepare_invoice_lines(self, include_mob, include_demob):
        self.ensure_one()
        rental = self.env.ref('dvz_equipment_rental_billing.product_equipment_rental')
        extra = self.env.ref('dvz_equipment_rental_billing.product_equipment_extra_hours')
        period = '%s - %s' % (self.date_from, self.date_to)
        contract = self.contract_id
        commands = []
        if include_mob:
            commands.append(Command.create({
                'product_id': self.env.ref('dvz_equipment_rental_billing.product_equipment_mobilization').id,
                'name': _('Mobilization to %s', contract.site or contract.partner_id.name),
                'quantity': 1.0,
                'price_unit': contract.mobilization_fee,
            }))
        for rental_line in self.line_ids.contract_line_id:
            logs = self.line_ids.filtered(lambda l: l.contract_line_id == rental_line)
            equipment = rental_line.equipment_id.display_name
            regular = sum(logs.mapped('amount_regular'))
            if rental_line.rate_type == 'hour':
                hours = sum(logs.mapped('working_hours'))
                if regular:
                    commands.append(Command.create({
                        'product_id': rental.id,
                        'name': _('%(equipment)s - %(hours)s working hours - %(period)s',
                                  equipment=equipment, hours=hours, period=period),
                        'quantity': hours,
                        'price_unit': rental_line.rate,
                    }))
                topup = self._get_min_hours_topup(rental_line, logs)
                if topup:
                    commands.append(Command.create({
                        'product_id': rental.id,
                        'name': _('%(equipment)s - minimum hours top-up (%(min)s h guaranteed)',
                                  equipment=equipment, min=rental_line.min_hours),
                        'quantity': topup,
                        'price_unit': rental_line.rate,
                    }))
            elif regular:
                days = len(logs.filtered(lambda l: l.amount_regular))
                commands.append(Command.create({
                    'product_id': rental.id,
                    'name': _('%(equipment)s - %(days)s days at %(rate)s %(type)s - %(period)s',
                              equipment=equipment, days=days, rate='{:,.2f}'.format(rental_line.rate),
                              type=dict(rental_line._fields['rate_type']._description_selection(self.env))
                              .get(rental_line.rate_type), period=period),
                    'quantity': 1.0,
                    'price_unit': regular,
                }))
            extra_amount = sum(logs.mapped('amount_extra'))
            if extra_amount:
                extra_hours = sum(logs.mapped('extra_hours'))
                commands.append(Command.create({
                    'product_id': extra.id,
                    'name': _('%(equipment)s - %(hours)s extra hours - %(period)s',
                              equipment=equipment, hours=extra_hours, period=period),
                    'quantity': 1.0,
                    'price_unit': extra_amount,
                }))
        if include_demob:
            commands.append(Command.create({
                'product_id': self.env.ref('dvz_equipment_rental_billing.product_equipment_demobilization').id,
                'name': _('Demobilization from %s', contract.site or contract.partner_id.name),
                'quantity': 1.0,
                'price_unit': contract.demobilization_fee,
            }))
        return commands

    def action_create_invoice(self):
        invoices = self.env['account.move']
        for sheet in self:
            if sheet.state != 'approved':
                raise UserError(_('Log sheet %s must be approved by the client before invoicing.', sheet.name))
            if sheet.invoice_id and sheet.invoice_id.state != 'cancel':
                raise UserError(_('Log sheet %s is already invoiced.', sheet.name))
            contract = sheet.contract_id
            # invoices created earlier in this loop (bulk invoicing) must be seen
            contract.invalidate_recordset(['mobilization_invoiced', 'demobilization_invoiced',
                                           'invoice_count', 'amount_invoiced'])
            include_mob = bool(contract.mobilization_fee and not contract.mobilization_invoiced)
            include_demob = bool(contract.demobilization_fee and not contract.demobilization_invoiced
                                 and contract.state == 'returned')
            lines = sheet._prepare_invoice_lines(include_mob, include_demob)
            if not lines:
                raise UserError(_('Nothing to invoice on %s. Check the rates on the rental.', sheet.name))
            invoice = self.env['account.move'].with_company(sheet.company_id).create({
                'move_type': 'out_invoice',
                'partner_id': sheet.partner_id.id,
                'company_id': sheet.company_id.id,
                'invoice_date': fields.Date.context_today(self),
                'ref': '%s / %s' % (contract.client_reference or contract.name, sheet.name),
                'invoice_origin': sheet.name,
                'dv_logsheet_id': sheet.id,
                'dv_rental_contract_id': contract.id,
                'dv_includes_mobilization': include_mob,
                'dv_includes_demobilization': include_demob,
                'invoice_line_ids': lines,
            })
            sheet.invoice_id = invoice
            sheet.message_post(body=_('Invoice %s created.', invoice._get_html_link()))
            invoices |= invoice
        return self._action_open_invoices(invoices)

    @api.model
    def _action_open_invoices(self, invoices):
        action = self.env['ir.actions.act_window']._for_xml_id('account.action_move_out_invoice_type')
        if len(invoices) == 1:
            action.update({
                'views': [(self.env.ref('account.view_move_form').id, 'form')],
                'res_id': invoices.id,
            })
        else:
            action['domain'] = [('id', 'in', invoices.ids)]
        return action

    def action_view_invoice(self):
        self.ensure_one()
        return self._action_open_invoices(self.invoice_id)


class EquipmentLogsheetLine(models.Model):
    _inherit = 'dvz.equipment.logsheet.line'

    currency_id = fields.Many2one(related='sheet_id.contract_id.currency_id')
    rate_type = fields.Selection(related='contract_line_id.rate_type')
    rate = fields.Monetary(related='contract_line_id.rate', currency_field='currency_id')
    extra_hours = fields.Float(compute='_compute_amounts', store=True)
    # Float (not Monetary) on purpose: daily prorations are kept unrounded so that a full month
    # adds up to the exact monthly rate. Amounts are rounded once per machine on the invoice.
    amount_regular = fields.Float(string='Rental Amount', compute='_compute_amounts', store=True)
    amount_extra = fields.Float(string='Extra Hours Amount', compute='_compute_amounts', store=True)
    amount_total = fields.Float(string='Amount', compute='_compute_amounts', store=True)

    @api.depends('contract_line_id.rate', 'contract_line_id.rate_type', 'date', 'working_hours', 'idle_hours',
                 'company_id.dv_eq_daily_hours', 'company_id.dv_eq_week_days', 'company_id.dv_eq_extra_factor')
    def _compute_amounts(self):
        for line in self:
            rate = line.contract_line_id.rate
            rate_type = line.contract_line_id.rate_type
            daily_hours = line.company_id.dv_eq_daily_hours or 10.0
            factor = line.company_id.dv_eq_extra_factor or 1.0
            regular = extra_hours = extra_amount = 0.0
            if rate_type == 'hour':
                # hourly rentals: only working hours are billed (minimum hours are topped up on the invoice)
                regular = line.working_hours * rate
            elif rate_type in ('day', 'week', 'month') and line.date:
                if rate_type == 'day':
                    day_rate = rate
                elif rate_type == 'week':
                    day_rate = rate / (line.company_id.dv_eq_week_days or 6)
                else:
                    day_rate = rate / working_days_in_month(line.date)
                # a day counts when the machine worked or stood by on site; full breakdown days are not billed
                if line.working_hours or line.idle_hours:
                    regular = day_rate
                extra_hours = max(line.working_hours - daily_hours, 0.0)
                extra_amount = extra_hours * (day_rate / daily_hours) * factor
            line.amount_regular = regular
            line.extra_hours = extra_hours
            line.amount_extra = extra_amount
            line.amount_total = regular + extra_amount
