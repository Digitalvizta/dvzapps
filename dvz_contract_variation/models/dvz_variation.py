from datetime import timedelta

from odoo import _, api, fields, models
from odoo.exceptions import UserError, ValidationError


class DvzContractVariation(models.Model):
    _name = 'dvz.contract.variation'
    _description = 'Variation Order'
    _inherit = ['mail.thread', 'mail.activity.mixin']
    _order = 'date desc, id desc'
    _check_company_auto = True

    name = fields.Char('Reference', required=True, copy=False, readonly=True, default=lambda self: _('New'))
    title = fields.Char('Subject', required=True, tracking=True)
    contract_id = fields.Many2one(
        'dvz.contract', 'Contract', required=True, index=True, tracking=True, check_company=True,
        domain="[('state', 'in', ('progress', 'handover'))]")
    partner_id = fields.Many2one(related='contract_id.partner_id', store=True)
    company_id = fields.Many2one(related='contract_id.company_id', store=True, index=True)
    currency_id = fields.Many2one(related='contract_id.currency_id', store=True)
    date = fields.Date('Date', required=True, default=fields.Date.context_today, tracking=True)
    reason = fields.Selection([
        ('client_instruction', 'Client instruction'),
        ('design_change', 'Design change'),
        ('site_condition', 'Site condition'),
        ('omission', 'Omission'),
        ('other', 'Other'),
    ], string='Reason', required=True, default='client_instruction', tracking=True)
    instruction_ref = fields.Char('Instruction Reference', help='Site instruction, letter or drawing reference.')
    description = fields.Html('Description')
    time_extension_days = fields.Integer('Time Extension (days)')
    state = fields.Selection([
        ('draft', 'Draft'),
        ('submitted', 'Submitted'),
        ('approved', 'Approved'),
        ('applied', 'Applied'),
        ('rejected', 'Rejected'),
    ], default='draft', required=True, tracking=True, copy=False, index=True)
    line_ids = fields.One2many('dvz.contract.variation.line', 'variation_id', 'Changes', copy=True)
    amount_total = fields.Monetary('Variation Value', compute='_compute_amount_total', store=True, tracking=True)
    approved_by_id = fields.Many2one('res.users', 'Approved By', copy=False, readonly=True)
    approved_date = fields.Date('Approved On', copy=False, readonly=True)
    applied_line_ids = fields.One2many('dvz.contract.line', 'variation_id', 'BOQ Lines Added', readonly=True)

    @api.depends('line_ids.price_subtotal')
    def _compute_amount_total(self):
        for rec in self:
            rec.amount_total = sum(rec.line_ids.mapped('price_subtotal'))

    @api.model_create_multi
    def create(self, vals_list):
        for vals in vals_list:
            if vals.get('name', _('New')) == _('New'):
                contract = self.env['dvz.contract'].browse(vals.get('contract_id'))
                vals['name'] = self.env['ir.sequence'].with_company(contract.company_id or self.env.company).next_by_code(
                    'dvz.contract.variation') or _('New')
        return super().create(vals_list)

    def unlink(self):
        if any(v.state not in ('draft', 'rejected') for v in self):
            raise UserError(_('Only draft or rejected variations can be deleted.'))
        return super().unlink()

    @api.constrains('line_ids', 'state')
    def _check_omissions(self):
        for rec in self:
            if rec.company_id.dvz_variation_allow_omission:
                continue
            if any(l.quantity < 0 or l.price_subtotal < 0 for l in rec.line_ids):
                raise ValidationError(_('Omissions (negative variations) are not allowed in Settings > Contracting.'))

    # ------------------------------------------------------------------
    def action_submit(self):
        for rec in self.filtered(lambda v: v.state == 'draft'):
            if not rec.line_ids and not rec.time_extension_days:
                raise UserError(_('Add at least one change or a time extension.'))
            if rec.company_id.dvz_variation_approval:
                rec.state = 'submitted'
                if rec.contract_id.user_id:
                    rec.activity_schedule('mail.mail_activity_data_todo', user_id=rec.contract_id.user_id.id,
                                          summary=_('Approve variation %s', rec.name))
            else:
                rec._do_approve()
        return True

    def _do_approve(self):
        for rec in self:
            rec.write({'state': 'approved', 'approved_by_id': self.env.user.id,
                       'approved_date': fields.Date.context_today(rec)})
            rec.activity_feedback(['mail.mail_activity_data_todo'])
            if rec.company_id.dvz_variation_auto_apply:
                rec.action_apply()

    def action_approve(self):
        if not self.env.user.has_group('dvz_contract.group_dvz_contract_manager'):
            raise UserError(_('Only contracting managers can approve variations.'))
        self.filtered(lambda v: v.state == 'submitted')._do_approve()
        return True

    def action_reject(self):
        self.filtered(lambda v: v.state in ('draft', 'submitted', 'approved')).write({'state': 'rejected'})
        self.activity_unlink(['mail.mail_activity_data_todo'])
        return True

    def action_draft(self):
        self.filtered(lambda v: v.state in ('submitted', 'rejected', 'approved')).write(
            {'state': 'draft', 'approved_by_id': False, 'approved_date': False})
        return True

    def action_apply(self):
        """Add auditable variation lines to the contract BOQ and update dates."""
        ContractLine = self.env['dvz.contract.line'].with_context(dvz_boq_unlock=True)
        for rec in self:
            if rec.state != 'approved':
                raise UserError(_('Only approved variations can be applied.'))
            contract = rec.contract_id
            last_seq = max(contract.line_ids.mapped('sequence') or [0])
            vals_list = [{
                'contract_id': contract.id,
                'display_type': 'line_section',
                'name': _('Variation %(name)s - %(title)s', name=rec.name, title=rec.title),
                'sequence': last_seq + 1,
                'variation_id': rec.id,
                'quantity': 0.0,
            }]
            seq = last_seq + 1
            for line in rec.line_ids:
                seq += 1
                base = line.contract_line_id
                vals_list.append({
                    'contract_id': contract.id,
                    'sequence': seq,
                    'item_no': line.item_no or (base and '%s-V' % (base.item_no or '')) or False,
                    'name': line.name if line.change_type == 'new' else _(
                        '%(desc)s (change to item %(item)s)', desc=line.name, item=base.item_no or base.name),
                    'product_id': line.product_id.id or base.product_id.id,
                    'uom_id': line.uom_id.id or base.uom_id.id,
                    'quantity': line.quantity,
                    'price_unit': line.price_unit,
                    'cost_unit': line.cost_unit,
                    'variation_id': rec.id,
                    'origin_line_id': base.id,
                })
            ContractLine.create(vals_list)
            if rec.time_extension_days and contract.date_end:
                contract.date_end = contract.date_end + timedelta(days=rec.time_extension_days)
            rec.state = 'applied'
            contract.message_post(body=_('Variation %(name)s applied: %(amount)s', name=rec.name,
                                         amount=rec.currency_id.format(rec.amount_total) if rec.currency_id else rec.amount_total))
        return True


class DvzContractVariationLine(models.Model):
    _name = 'dvz.contract.variation.line'
    _description = 'Variation Order Line'
    _order = 'variation_id, sequence, id'

    variation_id = fields.Many2one('dvz.contract.variation', required=True, ondelete='cascade', index=True)
    contract_id = fields.Many2one(related='variation_id.contract_id')
    company_id = fields.Many2one(related='variation_id.company_id', store=True)
    currency_id = fields.Many2one(related='variation_id.currency_id', store=True)
    sequence = fields.Integer(default=10)
    change_type = fields.Selection(
        [('new', 'New item'), ('change', 'Change to existing item')],
        string='Change', required=True, default='new')
    contract_line_id = fields.Many2one(
        'dvz.contract.line', 'Existing Item',
        domain="[('contract_id', '=', contract_id), ('display_type', '=', False)]")
    item_no = fields.Char('Item No.')
    product_id = fields.Many2one('product.product', 'Product / Work Item')
    name = fields.Text('Description', required=True)
    uom_id = fields.Many2one('uom.uom', 'Unit')
    quantity = fields.Float('Quantity (+/-)', digits='Product Unit', default=1.0,
                            help='For a change, the quantity added (positive) or omitted (negative).')
    price_unit = fields.Monetary('Rate')
    cost_unit = fields.Monetary('Est. Unit Cost')
    price_subtotal = fields.Monetary('Amount', compute='_compute_subtotal', store=True)

    @api.depends('quantity', 'price_unit')
    def _compute_subtotal(self):
        for line in self:
            line.price_subtotal = line.quantity * line.price_unit

    @api.onchange('contract_line_id')
    def _onchange_contract_line_id(self):
        base = self.contract_line_id
        if base:
            self.item_no = base.item_no
            self.name = base.name
            self.uom_id = base.uom_id
            self.price_unit = base.price_unit
            self.cost_unit = base.cost_unit
            self.product_id = base.product_id

    @api.onchange('product_id')
    def _onchange_product_id(self):
        if self.product_id and self.change_type == 'new':
            self.name = self.product_id.display_name
            self.uom_id = self.product_id.uom_id
            if not self.price_unit:
                self.price_unit = self.product_id.lst_price

    @api.constrains('change_type', 'contract_line_id')
    def _check_change(self):
        for line in self:
            if line.change_type == 'change' and not line.contract_line_id:
                raise ValidationError(_('Select the existing BOQ item to change.'))


class DvzContractLine(models.Model):
    _inherit = 'dvz.contract.line'

    variation_id = fields.Many2one('dvz.contract.variation', 'Variation', readonly=True, index='btree_not_null', ondelete='restrict')
    origin_line_id = fields.Many2one('dvz.contract.line', 'Original Item', readonly=True)
    is_variation = fields.Boolean(compute='_compute_is_variation', store=True)

    @api.depends('variation_id')
    def _compute_is_variation(self):
        for line in self:
            line.is_variation = bool(line.variation_id)
