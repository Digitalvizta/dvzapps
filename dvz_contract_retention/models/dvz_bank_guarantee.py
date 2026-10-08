from datetime import timedelta

from odoo import _, api, fields, models
from odoo.exceptions import ValidationError


class DvzBankGuarantee(models.Model):
    _name = 'dvz.bank.guarantee'
    _description = 'Bank Guarantee'
    _inherit = ['mail.thread', 'mail.activity.mixin']
    _order = 'expiry_date, id'
    _check_company_auto = True

    name = fields.Char('Guarantee No.', required=True, tracking=True)
    contract_id = fields.Many2one('dvz.contract', 'Contract', index=True, tracking=True, check_company=True)
    guarantee_type = fields.Selection([
        ('bid', 'Bid bond'),
        ('performance', 'Performance bond'),
        ('advance', 'Advance payment guarantee'),
        ('retention', 'Retention bond'),
        ('other', 'Other'),
    ], string='Type', required=True, default='performance', tracking=True)
    direction = fields.Selection([('given', 'Given (issued for us)'), ('received', 'Received (from subcontractor)')],
                                 required=True, default='given', tracking=True)
    partner_id = fields.Many2one('res.partner', 'Beneficiary / Issuer', tracking=True,
                                 help='Beneficiary for guarantees given, or the subcontractor for guarantees received.')
    bank_id = fields.Many2one('res.bank', 'Issuing Bank', tracking=True)
    company_id = fields.Many2one('res.company', required=True, default=lambda self: self.env.company, index=True)
    currency_id = fields.Many2one('res.currency', required=True, default=lambda self: self.env.company.currency_id)
    amount = fields.Monetary('Amount', required=True, tracking=True)
    commission_percent = fields.Float('Bank Commission %')
    commission_amount = fields.Monetary('Commission', compute='_compute_commission', store=True)
    issue_date = fields.Date('Issue Date', default=fields.Date.context_today)
    expiry_date = fields.Date('Expiry Date', required=True, tracking=True)
    days_to_expiry = fields.Integer('Days to Expiry', compute='_compute_days_to_expiry')
    expiry_status = fields.Selection(
        [('ok', 'Valid'), ('soon', 'Expiring soon'), ('expired', 'Expired')],
        compute='_compute_days_to_expiry', string='Expiry')
    state = fields.Selection([
        ('draft', 'Draft'),
        ('active', 'Active'),
        ('released', 'Released'),
        ('expired', 'Expired'),
        ('cancel', 'Cancelled'),
    ], default='active', required=True, tracking=True)
    notes = fields.Text('Notes')
    color = fields.Integer(compute='_compute_days_to_expiry')

    @api.depends('amount', 'commission_percent')
    def _compute_commission(self):
        for rec in self:
            rec.commission_amount = rec.amount * rec.commission_percent / 100.0

    def _compute_days_to_expiry(self):
        today = fields.Date.context_today(self)
        for rec in self:
            days = (rec.expiry_date - today).days if rec.expiry_date else 0
            rec.days_to_expiry = days
            reminder = rec.company_id.dvz_guarantee_reminder_days or 30
            if rec.expiry_date and days < 0:
                rec.expiry_status, rec.color = 'expired', 1
            elif rec.expiry_date and days <= reminder:
                rec.expiry_status, rec.color = 'soon', 2
            else:
                rec.expiry_status, rec.color = 'ok', 10

    @api.onchange('contract_id')
    def _onchange_contract_id(self):
        if self.contract_id:
            self.partner_id = self.contract_id.partner_id
            self.currency_id = self.contract_id.currency_id
            self.company_id = self.contract_id.company_id

    @api.constrains('issue_date', 'expiry_date')
    def _check_dates(self):
        for rec in self:
            if rec.issue_date and rec.expiry_date and rec.expiry_date < rec.issue_date:
                raise ValidationError(_('The expiry date cannot be before the issue date.'))

    def action_activate(self):
        self.write({'state': 'active'})

    def action_release(self):
        self.write({'state': 'released'})
        self.activity_unlink(['mail.mail_activity_data_todo'])

    def action_cancel(self):
        self.write({'state': 'cancel'})
        self.activity_unlink(['mail.mail_activity_data_todo'])

    @api.model
    def _cron_guarantee_reminders(self):
        today = fields.Date.context_today(self)
        for company in self.env['res.company'].search([]):
            days = company.dvz_guarantee_reminder_days or 30
            guarantees = self.search([
                ('company_id', '=', company.id),
                ('state', '=', 'active'),
                ('expiry_date', '<=', today + timedelta(days=days)),
            ])
            for gtee in guarantees:
                if gtee.expiry_date < today and company.dvz_guarantee_auto_expire:
                    gtee.state = 'expired'
                    gtee.activity_unlink(['mail.mail_activity_data_todo'])
                    continue
                if gtee.activity_ids:
                    continue
                user = gtee.contract_id.user_id or self.env.ref('base.user_admin', raise_if_not_found=False)
                if user:
                    gtee.activity_schedule(
                        'mail.mail_activity_data_todo', date_deadline=gtee.expiry_date, user_id=user.id,
                        summary=_('Bank guarantee %(name)s expires on %(date)s', name=gtee.name, date=gtee.expiry_date))
