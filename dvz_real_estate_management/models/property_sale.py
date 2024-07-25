# -*- coding: utf-8 -*-

from odoo import api, fields, models, _
from odoo.exceptions import ValidationError
from datetime import datetime, timedelta


class PropertySale(models.Model):
    """A class for the model property sale to represent
    the sale order of a property"""
    _name = 'property.sale'
    _description = 'Sale of the Property'
    _inherit = ['mail.thread', 'mail.activity.mixin']
    _order = 'name desc'

    name = fields.Char(string='Reference', readonly=True,
                       copy=False, default='New',
                       help='The reference code/sequence of the property sale')
    property_id = fields.Many2one(
        'property.property', required=True,
        domain="[('state', '=', 'available'), ('sale_rent', '=', 'for_sale')]",
        string="Property Name",
        help='The property to be sold')
    partner_id = fields.Many2one('res.partner', string="Customer",
                                 required=True,
                                 help='The customer who is buying the property')
    order_date = fields.Date(string="Order Date",
                             help='The order date of property')
    state = fields.Selection([('draft', 'Draft'), ('invisible', ''), ('confirm', 'Confirm')],
                             default='draft', string="State", tracking=True, domain=lambda self: [('state', '!=', 'invisible')])
    invoice_id = fields.Many2one('account.move', readonly=True,
                                 string="Invoice",
                                 help='The invoice reference for the property')
    invoiced = fields.Boolean(string='Invoiced',
                              help='Is the property sale invoiced')
    billed = fields.Boolean(string='Commission Billed',
                            help='Is the commission given for this property '
                                 'sale')
    sale_price = fields.Monetary(string="Sale Price", readonly=False,
                                 related='property_id.unit_price',
                                 help='The price of the property')
    any_broker = fields.Boolean(string='Any Broker',
                                help="Enable if this sale have a Broker")
    broker_id = fields.Many2one('res.partner', string="Broker name",
                                help='The broker for this property sale')
    commission_plan_id = fields.Many2one('property.commission',
                                         string="Commission Plan",
                                         help="Select the Commission Plan for "
                                              "the broker")
    commission_type = fields.Char(
        compute='_compute_commission_and_commission_type',
        string="Commission Type",
        help='The type of the commission')
    commission = fields.Monetary(string='Commission',
                                 compute='_compute_commission_and_commission_type',
                                 help='THe amount of commission')
    company_id = fields.Many2one('res.company',
                                 string="Property Management Company",
                                 default=lambda self: self.env.company)
    currency_id = fields.Many2one('res.currency', 'Currency',
                                  related='company_id.currency_id',
                                  required=True)
    is_installment_payment = fields.Boolean(string="Installment Payment", readonly=False,
                                 related='property_id.is_installment_payment',
                                 help='The price of the property')
    no_of_installments = fields.Integer(string="Number of Installments", related='property_id.no_of_installments')
    amount_per_installment = fields.Float(string="Amount Per Installment", related='property_id.amount_per_installment')
    property_sale_line_ids = fields.One2many('property.sale.line', 'property_sale_id', string="Property Sale Line")

    @api.model
    def create(self, vals):
        """Generate Reference for the sale order"""
        if vals.get('name', _('New')) == _('New'):
            vals['name'] = self.env['ir.sequence'].next_by_code(
                'property.sale') or 'New'
        res = super(PropertySale, self).create(vals)
        return res

    @api.depends('commission_plan_id', 'sale_price')
    def _compute_commission_and_commission_type(self):
        """Calculate commission based on commission plan and sale price"""
        for rec in self:
            rec.commission_type = rec.commission_plan_id.commission_type
            if rec.commission_plan_id.commission_type == 'fixed':
                rec.commission = rec.commission_plan_id.commission
            else:
                rec.commission = (rec.sale_price *
                                  rec.commission_plan_id.commission / 100)

    def create_invoice(self):
        """Generate Invoice Based on the Monetary Values and return
        Invoice Form View"""
        self.invoiced = True
        return {
            'name': _('Invoice'),
            'view_mode': 'form',
            'res_model': 'account.move',
            'target': 'current',
            'type': 'ir.actions.act_window',
            'context': {
                'default_move_type': 'out_invoice',
                'default_company_id': self.env.user.company_id.id,
                'default_partner_id': self.partner_id.id,
                'default_property_order_id': self.id,
                'default_invoice_line_ids': [fields.Command.create({
                    'name': self.property_id.name,
                    'price_unit': self.sale_price,
                    'currency_id': self.env.user.company_id.currency_id.id,
                })]
            }
        }

    def commission_bill(self):
        """Generate Bills Based on the Monetary Values and return
            Bills Form View"""
        self.billed = True
        return {
            'name': _('Commission Bill'),
            'view_mode': 'form',
            'res_model': 'account.move',
            'target': 'current',
            'type': 'ir.actions.act_window',
            'context': {
                'default_move_type': 'in_invoice',
                'default_company_id': self.env.user.company_id.id,
                'default_partner_id': self.broker_id.id,
                'default_property_order_id': self.id,
                'default_invoice_line_ids': [fields.Command.create({
                    'name': self.property_id.name,
                    'price_unit': self.commission,
                    'currency_id': self.env.user.company_id.currency_id.id,
                })]
            }
        }

    def action_view_invoice(self):
        """Return Invoices Tree View"""
        return {
            'name': _('Invoices'),
            'view_mode': 'tree,form',
            'res_model': 'account.move',
            'target': 'current',
            'type': 'ir.actions.act_window',
            'domain': [('property_order_id', '=', self.id),
                       ('move_type', '=', 'out_invoice')]
        }

    def action_view_commission_bill(self):
        """Return Bills Tree View"""
        return {
            'name': _('Commission Bills'),
            'view_mode': 'tree,form',
            'res_model': 'account.move',
            'target': 'current',
            'type': 'ir.actions.act_window',
            'domain': [('property_order_id', '=', self.id),
                       ('move_type', '=', 'in_invoice')]
        }

    def action_confirm(self):
        """Confirm the sale order and Change necessary fields"""
        if self.partner_id.blacklisted:
            raise ValidationError(
                _('The Customer %r is Blacklisted.', self.partner_id.name))
        self.state = 'confirm'
        self.property_id.state = 'sold'
        self.property_id.sale_id = self.id
    
    @api.onchange('is_installment_payment')
    def onchange_installment(self):
        ''' This method is used to compute the installment amortization line '''
        if self.is_installment_payment:
            self.property_sale_line_ids = [(5, 0, 0)]
            property_sale_line_ids = []
            for i in range(1, self.no_of_installments + 1): 
                property_sale_line_ids.append((0, 0, {
                    'serial_number': i,
                    'capital_repayment': self.amount_per_installment,
                    'remaining_capital': self.sale_price - (self.amount_per_installment * i),
                    }))
            self.property_sale_line_ids = property_sale_line_ids
    
    @api.onchange('property_id',  'property_sale_line_ids')
    def onchange_show_confirm(self):
        if self.is_installment_payment:
            total_amount = 0.00
            self.state = 'invisible'
            if self.property_sale_line_ids:
                for rec in self.property_sale_line_ids:
                    total_amount += rec.collection_amount
                if self.sale_price == round(total_amount, 1):
                    self.state = 'draft'
                else:
                    self.state = 'invisible'
        else:
            self.state = 'draft'



class PropertySaleLine(models.Model):
    """A class for the model property sale line to represent
    the installment payment of a property"""
    _name = 'property.sale.line'
    _description = 'Sale of the Property'
    _order = 'id'
    
    property_sale_id = fields.Many2one('property.sale', string="Property Sale")
    name = fields.Integer(string='Installment No')
    serial_number = fields.Integer(string='Installment No')
    remaining_capital = fields.Float(string='Remaining Capital')
    capital_repayment = fields.Float(string='Capital Repayment')
    collection_status = fields.Boolean(string='Collection Status')
    collection_amount = fields.Float(string='Collection Amount')
    collection_date = fields.Date(string='Collection Date')

    @api.onchange('collection_status')
    def onchange_collection_status(self):
        for rec in self:
            if rec.collection_status:
                rec.collection_date = datetime.now()
                rec.collection_amount = rec.capital_repayment