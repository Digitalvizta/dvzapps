from odoo import Command, _, api, fields, models
from odoo.exceptions import UserError


class ManpowerTimesheet(models.Model):
    _inherit = 'dvz.manpower.timesheet'

    currency_id = fields.Many2one(related='contract_id.currency_id')
    amount_total = fields.Monetary(
        string='Amount (excl. VAT)', compute='_compute_amount_total', store=True, currency_field='currency_id')
    invoice_id = fields.Many2one('account.move', string='Invoice', readonly=True, copy=False, tracking=True)
    invoice_state = fields.Selection(related='invoice_id.state', string='Invoice Status')
    invoice_payment_state = fields.Selection(related='invoice_id.payment_state', string='Payment Status')

    @api.depends('line_ids.amount_total')
    def _compute_amount_total(self):
        for sheet in self:
            sheet.amount_total = sum(sheet.line_ids.mapped('amount_total'))

    def _prepare_invoice_lines(self):
        self.ensure_one()
        service = self.env.ref('dvz_manpower_billing.product_manpower_service')
        overtime = self.env.ref('dvz_manpower_billing.product_manpower_overtime')
        period = '%s - %s' % (self.date_from, self.date_to)
        commands = []
        for line in self.line_ids.filtered(lambda l: l.amount_regular or l.amount_overtime):
            label = '%s (%s)' % (line.employee_id.name, line.job_id.name or '')
            if line.amount_regular:
                commands.append(Command.create({
                    'product_id': service.id,
                    'name': _('%(label)s - %(days)s days - %(period)s',
                              label=label, days=line.days_worked, period=period),
                    'quantity': 1.0,
                    'price_unit': line.amount_regular,
                }))
            if line.amount_overtime:
                commands.append(Command.create({
                    'product_id': overtime.id,
                    'name': _('%(label)s - Overtime %(hours)s h - %(period)s',
                              label=label, hours=line.overtime_hours, period=period),
                    'quantity': line.overtime_hours,
                    'price_unit': line.amount_overtime / line.overtime_hours if line.overtime_hours else line.amount_overtime,
                }))
        return commands

    def action_create_invoice(self):
        invoices = self.env['account.move']
        for sheet in self:
            if sheet.state != 'approved':
                raise UserError(_('Timesheet %s must be approved by the client before invoicing.', sheet.name))
            if sheet.invoice_id and sheet.invoice_id.state != 'cancel':
                raise UserError(_('Timesheet %s is already invoiced.', sheet.name))
            lines = sheet._prepare_invoice_lines()
            if not lines:
                raise UserError(_('Nothing to invoice on %s. Check the rates on the contract.', sheet.name))
            invoice = self.env['account.move'].with_company(sheet.company_id).create({
                'move_type': 'out_invoice',
                'partner_id': sheet.partner_id.id,
                'company_id': sheet.company_id.id,
                'invoice_date': fields.Date.context_today(self),
                'ref': '%s / %s' % (sheet.contract_id.client_reference or sheet.contract_id.name, sheet.name),
                'invoice_origin': sheet.name,
                'dv_timesheet_id': sheet.id,
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


class ManpowerTimesheetLine(models.Model):
    _inherit = 'dvz.manpower.timesheet.line'

    currency_id = fields.Many2one(related='sheet_id.contract_id.currency_id')
    rate_line_id = fields.Many2one(
        'dvz.manpower.contract.line', string='Rate', compute='_compute_rate_line_id', store=True, readonly=False,
        domain="[('contract_id', '=', contract_id)]")
    rate_type = fields.Selection(related='rate_line_id.rate_type')
    amount_regular = fields.Monetary(compute='_compute_amounts', store=True, currency_field='currency_id')
    amount_overtime = fields.Monetary(compute='_compute_amounts', store=True, currency_field='currency_id')
    amount_total = fields.Monetary(
        string='Amount', compute='_compute_amounts', store=True, currency_field='currency_id')

    @api.depends('job_id', 'sheet_id.contract_id', 'sheet_id.contract_id.line_ids.job_id')
    def _compute_rate_line_id(self):
        for line in self:
            rates = line.sheet_id.contract_id.line_ids
            line.rate_line_id = rates.filtered(lambda r: r.job_id == line.job_id)[:1] or rates[:1]

    @api.depends('rate_line_id.rate', 'rate_line_id.rate_type', 'days_worked', 'regular_hours',
                 'overtime_hours', 'sheet_id.date_from', 'sheet_id.date_to',
                 'company_id.dv_daily_hours', 'company_id.dv_overtime_factor')
    def _compute_amounts(self):
        for line in self:
            rate = line.rate_line_id.rate
            daily_hours = line.company_id.dv_daily_hours or 8.0
            factor = line.company_id.dv_overtime_factor or 1.5
            if line.rate_type == 'hour':
                hourly = rate
                regular = line.regular_hours * rate
            elif line.rate_type == 'day':
                hourly = rate / daily_hours
                regular = line.days_worked * rate
            elif line.rate_type == 'month':
                # Monthly rate prorated on the working days of the period (Fridays excluded)
                sheet = line.sheet_id
                period_days = sheet._count_working_days(sheet.date_from, sheet.date_to) \
                    if sheet.date_from and sheet.date_to else 0
                period_days = period_days or 26
                hourly = rate / period_days / daily_hours
                regular = rate * min(line.days_worked / period_days, 1.0)
            else:
                hourly = regular = 0.0
            line.amount_regular = regular
            line.amount_overtime = line.overtime_hours * hourly * factor
            line.amount_total = line.amount_regular + line.amount_overtime
