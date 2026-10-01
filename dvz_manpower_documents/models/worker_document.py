from datetime import timedelta

from odoo import _, api, fields, models

DOCUMENT_TYPES = [
    ('iqama', 'Iqama (Residence Permit)'),
    ('passport', 'Passport'),
    ('ajeer', 'Ajeer Permit'),
    ('medical', 'Medical Certificate'),
    ('insurance', 'Medical Insurance'),
    ('driving', 'Driving Licence'),
    ('other', 'Other'),
]


class WorkerDocument(models.Model):
    _name = 'dvz.worker.document'
    _description = 'Worker Document'
    _inherit = ['mail.thread', 'mail.activity.mixin']
    _order = 'expiry_date asc, id'
    _rec_name = 'display_label'

    employee_id = fields.Many2one('hr.employee', string='Worker', required=True, index=True, tracking=True)
    company_id = fields.Many2one(related='employee_id.company_id', store=True)
    doc_type = fields.Selection(DOCUMENT_TYPES, string='Document Type', required=True, default='iqama', tracking=True)
    number = fields.Char(string='Document Number', tracking=True)
    issue_date = fields.Date(string='Issue Date')
    expiry_date = fields.Date(string='Expiry Date', tracking=True)
    contract_id = fields.Many2one(
        'dvz.manpower.contract', string='Supply Contract',
        help='For Ajeer permits: the client contract this permit was issued for.')
    partner_id = fields.Many2one(related='contract_id.partner_id', string='Client', store=True)
    attachment_ids = fields.Many2many('ir.attachment', string='Scanned Copies')
    notes = fields.Text()
    display_label = fields.Char(compute='_compute_display_label', store=True)
    days_to_expiry = fields.Integer(compute='_compute_days_to_expiry')
    status = fields.Selection([
        ('valid', 'Valid'),
        ('expiring', 'Expiring Soon'),
        ('expired', 'Expired'),
        ('no_date', 'No Expiry Date'),
    ], compute='_compute_status', store=True, string='Status')

    @api.depends('doc_type', 'number', 'employee_id.name')
    def _compute_display_label(self):
        labels = dict(DOCUMENT_TYPES)
        for doc in self:
            parts = [labels.get(doc.doc_type, ''), doc.number or '', doc.employee_id.name or '']
            doc.display_label = ' - '.join(p for p in parts if p)

    @api.depends('expiry_date')
    def _compute_days_to_expiry(self):
        today = fields.Date.context_today(self)
        for doc in self:
            doc.days_to_expiry = (doc.expiry_date - today).days if doc.expiry_date else 0

    @api.depends('expiry_date', 'company_id.dv_doc_alert_days')
    def _compute_status(self):
        today = fields.Date.context_today(self)
        for doc in self:
            if not doc.expiry_date:
                doc.status = 'no_date'
            elif doc.expiry_date < today:
                doc.status = 'expired'
            elif doc.expiry_date <= today + timedelta(days=doc.company_id.dv_doc_alert_days or 30):
                doc.status = 'expiring'
            else:
                doc.status = 'valid'

    def _get_alert_user(self):
        self.ensure_one()
        return (self.contract_id.user_id
                or self.employee_id.dv_current_contract_id.user_id
                or self.employee_id.parent_id.user_id
                or self.env.ref('base.user_admin', raise_if_not_found=False)
                or self.env.user)

    @api.model
    def _cron_check_expiry(self):
        documents = self.search([('expiry_date', '!=', False), ('employee_id.active', '=', True)])
        # status depends on today's date: recompute it every day
        self.env.add_to_compute(self._fields['status'], documents)
        documents.flush_recordset(['status'])
        todo_type = self.env.ref('mail.mail_activity_data_todo', raise_if_not_found=False)
        for doc in documents.filtered(lambda d: d.status in ('expiring', 'expired')):
            if doc.activity_ids.filtered(lambda a: a.activity_type_id == todo_type):
                continue
            doc.activity_schedule(
                'mail.mail_activity_data_todo',
                date_deadline=doc.expiry_date,
                summary=_('Renew %s', doc.display_label),
                note=_('This document expires on %s. Please start the renewal.', doc.expiry_date),
                user_id=doc._get_alert_user().id,
            )
