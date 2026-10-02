from datetime import timedelta

from odoo import _, api, fields, models

DOCUMENT_TYPES = [
    ('registration', 'Registration (Istimara)'),
    ('insurance', 'Insurance'),
    ('tpi', 'TPI / Third-Party Inspection'),
    ('mvpi', 'Periodic Inspection (MVPI / Fahas)'),
    ('operator', 'Operator Card / Licence'),
    ('other', 'Other'),
]


class EquipmentDocument(models.Model):
    _name = 'dvz.equipment.document'
    _description = 'Equipment Document'
    _inherit = ['mail.thread', 'mail.activity.mixin']
    _order = 'expiry_date asc, id'
    _rec_name = 'display_label'

    equipment_id = fields.Many2one('dvz.equipment', string='Equipment', required=True, index=True, tracking=True)
    company_id = fields.Many2one(related='equipment_id.company_id', store=True)
    doc_type = fields.Selection(DOCUMENT_TYPES, string='Document Type', required=True, default='registration',
                                tracking=True)
    number = fields.Char(string='Document Number', tracking=True)
    issuer = fields.Char(string='Issued By', help='Traffic department, insurance company or inspection body.')
    issue_date = fields.Date(string='Issue Date')
    expiry_date = fields.Date(string='Expiry Date', tracking=True)
    blocks_dispatch = fields.Boolean(
        string='Blocks Dispatch when Expired', default=True,
        help='The machine cannot be dispatched to a client while this document is expired.')
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

    @api.depends('doc_type', 'number', 'equipment_id.name', 'equipment_id.code')
    def _compute_display_label(self):
        labels = dict(DOCUMENT_TYPES)
        for doc in self:
            parts = [labels.get(doc.doc_type, ''), doc.number or '', doc.equipment_id.display_name or '']
            doc.display_label = ' - '.join(p for p in parts if p)

    @api.depends('expiry_date')
    def _compute_days_to_expiry(self):
        today = fields.Date.context_today(self)
        for doc in self:
            doc.days_to_expiry = (doc.expiry_date - today).days if doc.expiry_date else 0

    @api.depends('expiry_date', 'company_id.dv_eq_doc_alert_days')
    def _compute_status(self):
        today = fields.Date.context_today(self)
        for doc in self:
            if not doc.expiry_date:
                doc.status = 'no_date'
            elif doc.expiry_date < today:
                doc.status = 'expired'
            elif doc.expiry_date <= today + timedelta(days=doc.company_id.dv_eq_doc_alert_days or 30):
                doc.status = 'expiring'
            else:
                doc.status = 'valid'

    def _get_alert_user(self):
        self.ensure_one()
        return (self.equipment_id.current_contract_id.user_id
                or self.env.ref('base.user_admin', raise_if_not_found=False)
                or self.env.user)

    @api.model
    def _cron_check_expiry(self):
        documents = self.search([('expiry_date', '!=', False), ('equipment_id.active', '=', True)])
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
