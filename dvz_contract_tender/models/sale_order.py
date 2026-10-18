from dateutil.relativedelta import relativedelta
from markupsafe import Markup

from odoo import _, api, fields, models
from odoo.exceptions import UserError

TENDER_STATUS = [
    ('draft', 'Draft'),
    ('submitted', 'Submitted'),
    ('superseded', 'Superseded'),
    ('won', 'Won'),
    ('lost', 'Lost'),
    ('cancel', 'Cancelled'),
]


class SaleOrder(models.Model):
    _inherit = 'sale.order'

    dvz_is_tender = fields.Boolean('Construction Tender', index=True, copy=True)
    dvz_tender_status = fields.Selection(TENDER_STATUS, string='Tender Status', compute='_compute_dvz_tender_status',
                                         store=True, index=True)
    dvz_project_title = fields.Char('Tender / Project Title')
    dvz_closing_date = fields.Date('Submission Deadline')
    dvz_submitted_date = fields.Date('Submitted On', copy=False, readonly=True)
    dvz_date_start = fields.Date('Expected Start')
    dvz_duration_months = fields.Integer('Duration (months)', default=12)

    # revisions
    dvz_revision = fields.Integer('Revision', default=0, copy=False, readonly=True)
    dvz_revision_label = fields.Char('Rev.', compute='_compute_dvz_revision_label')
    dvz_revision_origin_id = fields.Many2one('sale.order', 'First Revision', copy=False, readonly=True,
                                             index='btree_not_null')
    dvz_revision_count = fields.Integer(compute='_compute_dvz_revision_count')
    dvz_superseded = fields.Boolean('Superseded', copy=False, readonly=True)
    dvz_revision_reason = fields.Char('Revision Reason', copy=False)

    # result
    dvz_lost = fields.Boolean('Lost', copy=False, readonly=True)
    dvz_lost_reason_id = fields.Many2one('crm.lost.reason', 'Lost Reason', copy=False, readonly=True)
    dvz_lost_note = fields.Text('Lost Note', copy=False, readonly=True)
    dvz_contract_id = fields.Many2one('dvz.contract', 'Contract', copy=False, readonly=True)

    # commercial terms (copied to the contract)
    dvz_retention_percent = fields.Float('Retention %', default=lambda self: self.env.company.dvz_retention_percent)
    dvz_advance_percent = fields.Float('Advance Payment %', default=lambda self: self.env.company.dvz_advance_percent)
    dvz_advance_recovery_percent = fields.Float(
        'Advance Recovery %', default=lambda self: self.env.company.dvz_advance_recovery_percent)
    dvz_defects_months = fields.Integer('Defects Liability (months)',
                                        default=lambda self: self.env.company.dvz_defects_months)

    # estimation
    dvz_overhead_percent = fields.Float('Overhead %', default=lambda self: self.env.company.dvz_tender_overhead_percent)
    dvz_profit_percent = fields.Float('Profit %', default=lambda self: self.env.company.dvz_tender_profit_percent)
    dvz_cost_total = fields.Monetary('Estimated Cost', compute='_compute_dvz_estimate', store=True)
    dvz_margin_total = fields.Monetary('Estimated Margin', compute='_compute_dvz_estimate', store=True)
    dvz_margin_percent = fields.Float('Margin %', compute='_compute_dvz_estimate', store=True, aggregator='avg')
    dvz_boq_product_id = fields.Many2one('product.product', compute='_compute_dvz_boq_product_id')

    dvz_scope = fields.Html('Scope & Inclusions')
    dvz_exclusions = fields.Html('Exclusions & Assumptions')
    dvz_guarantee_ids = fields.One2many('dvz.bank.guarantee', 'dvz_sale_order_id', 'Bid Bonds')
    dvz_bid_bond_count = fields.Integer(compute='_compute_dvz_bid_bond_count')

    # ------------------------------------------------------------------
    # computes
    # ------------------------------------------------------------------
    @api.depends('dvz_is_tender', 'state', 'dvz_superseded', 'dvz_lost')
    def _compute_dvz_tender_status(self):
        for order in self:
            if not order.dvz_is_tender:
                order.dvz_tender_status = False
            elif order.dvz_superseded:
                order.dvz_tender_status = 'superseded'
            elif order.dvz_lost:
                order.dvz_tender_status = 'lost'
            elif order.state == 'sale':
                order.dvz_tender_status = 'won'
            elif order.state == 'cancel':
                order.dvz_tender_status = 'cancel'
            elif order.state == 'sent':
                order.dvz_tender_status = 'submitted'
            else:
                order.dvz_tender_status = 'draft'

    @api.depends('dvz_revision')
    def _compute_dvz_revision_label(self):
        for order in self:
            order.dvz_revision_label = 'R%s' % (order.dvz_revision or 0)

    def _dvz_revision_group(self):
        self.ensure_one()
        origin = self.dvz_revision_origin_id or self
        if not origin.id:
            return self
        return self.with_context(active_test=False).search(
            ['|', ('id', '=', origin.id), ('dvz_revision_origin_id', '=', origin.id)], order='dvz_revision')

    def _compute_dvz_revision_count(self):
        for order in self:
            order.dvz_revision_count = len(order._dvz_revision_group()) if order.dvz_is_tender and order.id else 0

    @api.depends('order_line.dvz_cost_subtotal', 'order_line.price_subtotal', 'order_line.display_type')
    def _compute_dvz_estimate(self):
        for order in self:
            lines = order.order_line.filtered(lambda l: not l.display_type)
            cost = sum(lines.mapped('dvz_cost_subtotal'))
            value = sum(lines.mapped('price_subtotal'))
            order.dvz_cost_total = cost
            order.dvz_margin_total = value - cost if cost else 0.0
            order.dvz_margin_percent = (value - cost) / value * 100.0 if (value and cost) else 0.0

    def _compute_dvz_boq_product_id(self):
        default = self.env.ref('dvz_contract_tender.product_boq_item', raise_if_not_found=False)
        for order in self:
            order.dvz_boq_product_id = order.company_id.dvz_tender_product_id or default

    def _compute_dvz_bid_bond_count(self):
        for order in self:
            order.dvz_bid_bond_count = len(order.dvz_guarantee_ids)

    # ------------------------------------------------------------------
    # ORM
    # ------------------------------------------------------------------
    @api.model_create_multi
    def create(self, vals_list):
        for vals in vals_list:
            is_tender = vals.get('dvz_is_tender', self.env.context.get('default_dvz_is_tender'))
            if is_tender and vals.get('name', _('New')) == _('New'):
                company = self.env['res.company'].browse(vals.get('company_id')) if vals.get('company_id') \
                    else self.env.company
                vals['name'] = self.env['ir.sequence'].with_company(company).next_by_code('dvz.tender') or _('New')
        return super().create(vals_list)

    def write(self, vals):
        if vals.get('state') == 'sent':
            for order in self.filtered(lambda o: o.dvz_is_tender and not o.dvz_submitted_date):
                order.dvz_submitted_date = fields.Date.context_today(order)
        return super().write(vals)

    def get_formview_id(self, access_uid=None):
        if len(self) == 1 and self.dvz_is_tender:
            view = self.env.ref('dvz_contract_tender.dvz_tender_view_form', raise_if_not_found=False)
            if view:
                return view.id
        return super().get_formview_id(access_uid=access_uid)

    # ------------------------------------------------------------------
    # standard flow overrides
    # ------------------------------------------------------------------
    def _find_mail_template(self):
        if self.dvz_is_tender and self.state != 'sale' and not self.env.context.get('proforma'):
            template = self.env.ref('dvz_contract_tender.mail_template_dvz_tender', raise_if_not_found=False)
            if template:
                return template
        return super()._find_mail_template()

    def _create_invoices(self, grouped=False, final=False, date=None):
        if any(order.dvz_is_tender for order in self):
            raise UserError(_('Tenders are never invoiced. Invoice through the contract: advance invoice, '
                              'payment certificates and retention releases.'))
        return super()._create_invoices(grouped=grouped, final=final, date=date)

    def action_draft(self):
        if any(order.dvz_superseded or order.dvz_lost for order in self):
            raise UserError(_('A superseded or lost tender cannot be reopened. Create a new revision from the '
                              'latest one instead.'))
        return super().action_draft()

    def action_confirm(self):
        tenders = self.filtered('dvz_is_tender')
        if any(t.dvz_superseded or t.dvz_lost for t in tenders):
            raise UserError(_('Only the latest open revision of a tender can be marked as won.'))
        res = super().action_confirm()
        for tender in tenders:
            tender._dvz_on_won()
        return res

    # ------------------------------------------------------------------
    # tender actions
    # ------------------------------------------------------------------
    def _dvz_check_open_tender(self):
        for order in self:
            if not order.dvz_is_tender:
                raise UserError(_('%s is not a tender.', order.name))
            if order.dvz_superseded or order.dvz_lost or order.state not in ('draft', 'sent'):
                raise UserError(_('Tender %s is no longer open.', order.name))

    def action_dvz_calculate_rates(self):
        self._dvz_check_open_tender()
        for order in self:
            factor = (1 + order.dvz_overhead_percent / 100.0) * (1 + order.dvz_profit_percent / 100.0)
            for line in order.order_line.filtered(lambda l: not l.display_type and l.dvz_cost_unit):
                rate = order.currency_id.round(line.dvz_cost_unit * factor)
                line.write({'price_unit': rate, 'technical_price_unit': 0.0 if rate else 1.0})
            order.message_post(body=_('Rates calculated from cost + %(oh)s%% overhead + %(pr)s%% profit.',
                                      oh=order.dvz_overhead_percent, pr=order.dvz_profit_percent))
        return True

    def action_dvz_new_revision(self):
        self.ensure_one()
        self._dvz_check_open_tender()
        group = self._dvz_revision_group()
        if self != group.filtered(lambda o: not o.dvz_superseded)[-1:]:
            raise UserError(_('Create revisions from the latest revision only.'))
        origin = self.dvz_revision_origin_id or self
        number = max(group.mapped('dvz_revision') or [0]) + 1
        base = origin.name
        new = self.copy({
            'name': '%s-R%s' % (base, number),
            'dvz_revision': number,
            'dvz_revision_origin_id': origin.id,
            'opportunity_id': self.opportunity_id.id,
            'origin': self.origin,
            'dvz_is_tender': True,
        })
        self.write({'dvz_superseded': True})
        self._action_cancel()
        self.message_post(body=Markup(_('Superseded by revision <b>%s</b>.')) % new.name)
        new.message_post(body=Markup(_('Revision <b>R%(n)s</b> created from %(old)s.')) % {
            'n': number, 'old': self.name})
        return new._get_records_action(views=[(self.env.ref('dvz_contract_tender.dvz_tender_view_form').id, 'form')])

    def action_dvz_view_revisions(self):
        self.ensure_one()
        group = self._dvz_revision_group()
        return {
            'type': 'ir.actions.act_window',
            'name': _('Revisions of %s', (self.dvz_revision_origin_id or self).name),
            'res_model': 'sale.order',
            'view_mode': 'list,form',
            'views': [(self.env.ref('dvz_contract_tender.dvz_tender_view_list').id, 'list'),
                      (self.env.ref('dvz_contract_tender.dvz_tender_view_form').id, 'form')],
            'domain': [('id', 'in', group.ids)],
            'context': {'active_test': False},
        }

    def action_dvz_compare_revisions(self):
        self.ensure_one()
        group = self._dvz_revision_group()
        action = self.env['ir.actions.act_window']._for_xml_id('dvz_contract_tender.action_dvz_tender_compare')
        action['domain'] = [('order_id', 'in', group.ids), ('display_type', '=', False)]
        action['context'] = {'active_test': False}
        return action

    def action_dvz_mark_lost(self):
        self.ensure_one()
        self._dvz_check_open_tender()
        return {
            'type': 'ir.actions.act_window',
            'name': _('Tender Lost'),
            'res_model': 'dvz.tender.lost',
            'view_mode': 'form',
            'target': 'new',
            'context': {'default_order_id': self.id},
        }

    def action_dvz_bid_bond(self):
        self.ensure_one()
        if not self.dvz_is_tender:
            raise UserError(_('%s is not a tender.', self.name))
        today = fields.Date.context_today(self)
        guarantee = self.env['dvz.bank.guarantee'].create({
            'name': _('Bid bond %s', self.name),
            'guarantee_type': 'bid',
            'direction': 'given',
            'partner_id': self.partner_id.commercial_partner_id.id,
            'company_id': self.company_id.id,
            'currency_id': self.currency_id.id,
            'amount': self.currency_id.round(self.amount_untaxed * self.company_id.dvz_tender_bid_bond_percent / 100.0),
            'issue_date': today,
            'expiry_date': (self.dvz_closing_date or today) + relativedelta(days=90),
            'dvz_sale_order_id': self.id,
        })
        return {
            'type': 'ir.actions.act_window',
            'res_model': 'dvz.bank.guarantee',
            'res_id': guarantee.id,
            'view_mode': 'form',
        }

    def action_dvz_view_bid_bonds(self):
        self.ensure_one()
        return {
            'type': 'ir.actions.act_window',
            'name': _('Bid Bonds'),
            'res_model': 'dvz.bank.guarantee',
            'view_mode': 'list,form',
            'domain': [('dvz_sale_order_id', '=', self.id)],
            'context': {'default_dvz_sale_order_id': self.id, 'default_guarantee_type': 'bid',
                        'default_partner_id': self.partner_id.commercial_partner_id.id},
        }

    def action_dvz_view_contract(self):
        self.ensure_one()
        return {
            'type': 'ir.actions.act_window',
            'res_model': 'dvz.contract',
            'res_id': self.dvz_contract_id.id,
            'view_mode': 'form',
        }

    def action_dvz_create_contract(self):
        self.ensure_one()
        if not self.dvz_is_tender or self.state != 'sale':
            raise UserError(_('Mark the tender as won first.'))
        if not self.dvz_contract_id:
            self._dvz_create_contract()
        return self.action_dvz_view_contract()

    # ------------------------------------------------------------------
    def _dvz_on_won(self):
        self.ensure_one()
        others = self._dvz_revision_group().filtered(
            lambda o: o != self and o.state in ('draft', 'sent') and not o.dvz_superseded)
        if others:
            others.write({'dvz_superseded': True})
            others._action_cancel()
        if not self.dvz_contract_id:
            self._dvz_create_contract()
        if self.opportunity_id and self.opportunity_id.active and self.opportunity_id.probability < 100:
            self.opportunity_id.action_set_won()

    def _dvz_contract_line_vals(self):
        self.ensure_one()
        overhead = 1 + self.dvz_overhead_percent / 100.0
        commands = []
        for line in self.order_line.sorted(lambda l: (l.sequence, l.id)):
            if line.display_type in ('line_section', 'line_subsection'):
                commands.append((0, 0, {'display_type': 'line_section', 'name': line.name or '-',
                                        'sequence': line.sequence}))
                continue
            if line.display_type == 'line_note':
                commands.append((0, 0, {'display_type': 'line_note', 'name': line.name or '-',
                                        'sequence': line.sequence}))
                continue
            if line.display_type or line.is_downpayment:
                continue
            qty = line.product_uom_qty
            rate = line.price_subtotal / qty if qty else line.price_unit
            commands.append((0, 0, {
                'sequence': line.sequence,
                'item_no': line.dvz_item_no,
                'name': line.name or line.product_id.display_name,
                'uom_id': line.dvz_uom_id.id,
                'quantity': qty,
                'price_unit': self.currency_id.round(rate),
                'cost_unit': self.currency_id.round(line.dvz_cost_unit * overhead),
            }))
        return commands

    def _dvz_create_contract(self):
        self.ensure_one()
        title = self.dvz_project_title or (self.opportunity_id.name if self.opportunity_id else False) or self.name
        partner = self.partner_id.commercial_partner_id
        start = self.dvz_date_start or fields.Date.context_today(self)
        # sudo: creating projects needs Project / Administrator rights, which estimators usually lack
        project = self.env['project.project'].sudo().create({
            'name': title,
            'partner_id': partner.id,
            'company_id': self.company_id.id,
        })
        taxes = self.order_line.filtered(lambda l: not l.display_type).tax_ids
        vals = {
            'title': title,
            'partner_id': partner.id,
            'project_id': project.id,
            'company_id': self.company_id.id,
            'currency_id': self.currency_id.id,
            'date_start': start,
            'date_end': start + relativedelta(months=self.dvz_duration_months) if self.dvz_duration_months else False,
            'retention_percent': self.dvz_retention_percent,
            'advance_percent': self.dvz_advance_percent,
            'advance_recovery_percent': self.dvz_advance_recovery_percent,
            'defects_months': self.dvz_defects_months,
            'scope': self.dvz_scope,
            'notes': self.note,
            'dvz_sale_order_id': self.id,
            'line_ids': self._dvz_contract_line_vals(),
        }
        if taxes:
            vals['tax_ids'] = [(6, 0, taxes.ids)]
        contract = self.env['dvz.contract'].with_company(self.company_id).create(vals)
        self.dvz_contract_id = contract
        self.message_post(body=Markup(_('Tender won. Contract <b>%s</b> created in draft: check it and confirm '
                                        'it when it is signed.')) % contract.name)
        contract.message_post(body=Markup(_('Created from tender <b>%s</b>.')) % self.name)
        return contract


class SaleOrderLine(models.Model):
    _inherit = 'sale.order.line'

    dvz_item_no = fields.Char('Item No.')
    dvz_uom_id = fields.Many2one('uom.uom', 'BOQ Unit')
    dvz_cost_material = fields.Monetary('Material')
    dvz_cost_labour = fields.Monetary('Labour')
    dvz_cost_equipment = fields.Monetary('Equipment')
    dvz_cost_subcontract = fields.Monetary('Subcontract')
    dvz_cost_unit = fields.Monetary('Direct Unit Cost', compute='_compute_dvz_cost_unit', store=True, readonly=False,
                                    help='Material + labour + equipment + subcontract per unit. You can also type it '
                                         'directly when there is no breakdown.')
    dvz_rate_calc = fields.Monetary('Calculated Rate', compute='_compute_dvz_rate_calc',
                                    help='Direct cost + overhead % + profit %.')
    dvz_cost_subtotal = fields.Monetary('Est. Cost', compute='_compute_dvz_cost_subtotal', store=True,
                                        help='Quantity x direct cost, plus overhead.')

    @api.model_create_multi
    def create(self, vals_list):
        orders = self.env['sale.order'].browse({v['order_id'] for v in vals_list if v.get('order_id')})
        tenders = {o.id: o for o in orders if o.dvz_is_tender}
        for vals in vals_list:
            order = tenders.get(vals.get('order_id'))
            if order and vals.get('is_downpayment'):
                raise UserError(_('Tenders are never invoiced: no down payment on tender %s.', order.name))
            if order and not vals.get('display_type') and not vals.get('product_id') and not vals.get('is_downpayment'):
                product = order.dvz_boq_product_id
                if product:
                    vals['product_id'] = product.id
                    # the web client sends every field of a new line, empty ones included (False / [])
                    if not vals.get('product_uom_id'):
                        vals['product_uom_id'] = product.uom_id.id
                    if not vals.get('name'):
                        vals['name'] = product.display_name
                    if not vals.get('tax_ids'):
                        vals.pop('tax_ids', None)  # let the product taxes be computed
        return super().create(vals_list)

    @api.depends('dvz_cost_material', 'dvz_cost_labour', 'dvz_cost_equipment', 'dvz_cost_subcontract')
    def _compute_dvz_cost_unit(self):
        for line in self:
            parts = line.dvz_cost_material + line.dvz_cost_labour + line.dvz_cost_equipment + line.dvz_cost_subcontract
            if parts:
                line.dvz_cost_unit = parts
            elif not line.dvz_cost_unit:
                line.dvz_cost_unit = 0.0

    @api.depends('dvz_cost_unit', 'order_id.dvz_overhead_percent', 'order_id.dvz_profit_percent')
    def _compute_dvz_rate_calc(self):
        for line in self:
            order = line.order_id
            line.dvz_rate_calc = line.dvz_cost_unit * (1 + order.dvz_overhead_percent / 100.0) * \
                (1 + order.dvz_profit_percent / 100.0)

    @api.depends('dvz_cost_unit', 'product_uom_qty', 'display_type', 'order_id.dvz_overhead_percent')
    def _compute_dvz_cost_subtotal(self):
        for line in self:
            if line.display_type:
                line.dvz_cost_subtotal = 0.0
                continue
            line.dvz_cost_subtotal = line.product_uom_qty * line.dvz_cost_unit * \
                (1 + line.order_id.dvz_overhead_percent / 100.0)
