from datetime import timedelta

from markupsafe import Markup

from odoo import _, api, fields, models
from odoo.exceptions import UserError

DISCIPLINES = [
    ('civil', 'Civil'), ('structural', 'Structural'), ('architectural', 'Architectural'),
    ('mechanical', 'Mechanical (HVAC)'), ('electrical', 'Electrical'), ('plumbing', 'Plumbing & drainage'),
    ('fire', 'Fire fighting'), ('landscape', 'Landscape'), ('other', 'Other'),
]


class DvzRfi(models.Model):
    _name = 'dvz.rfi'
    _description = 'Request for Information (RFI)'
    _inherit = ['dvz.doc.mixin']
    _order = 'id desc'
    _dvz_sequence = 'dvz.rfi'
    _dvz_portal_prefix = 'rfi'

    subject = fields.Char('Subject', required=True, tracking=True)
    discipline = fields.Selection(DISCIPLINES, default='civil', tracking=True)
    priority = fields.Selection([('0', 'Normal'), ('1', 'Urgent')], default='0')
    reference = fields.Char('Drawing / Location', help='Drawing number, grid line, level or area this RFI is about.')
    question = fields.Text('Question', required=True)
    proposed_solution = fields.Text('Proposed Solution')
    state = fields.Selection([
        ('draft', 'Draft'), ('sent', 'Waiting for answer'), ('answered', 'Answered'), ('closed', 'Closed'),
        ('cancel', 'Cancelled'),
    ], default='draft', required=True, tracking=True, copy=False, index=True)
    date_sent = fields.Date('Sent On', readonly=True, copy=False)
    date_required = fields.Date('Answer Needed By', tracking=True)
    answer = fields.Text('Answer', tracking=True, copy=False)
    answered_by_id = fields.Many2one('res.partner', 'Answered By', readonly=True, copy=False)
    answer_date = fields.Datetime('Answered On', readonly=True, copy=False)
    answer_attachment_ids = fields.Many2many('ir.attachment', 'dvz_rfi_answer_attachment_rel', 'rfi_id',
                                             'attachment_id', string='Answer Documents', copy=False)
    cost_impact = fields.Boolean('Cost impact', tracking=True)
    time_impact = fields.Boolean('Time impact', tracking=True)
    impact_days = fields.Integer('Delay (days)')
    variation_id = fields.Many2one('dvz.contract.variation', 'Variation Order', copy=False, readonly=True)
    is_overdue = fields.Boolean('Overdue', compute='_compute_overdue', search='_search_overdue')
    days_open = fields.Integer('Days Open', compute='_compute_overdue')

    @api.depends('state', 'date_required', 'date_sent', 'answer_date')
    def _compute_overdue(self):
        today = fields.Date.context_today(self)
        for rec in self:
            rec.is_overdue = rec.state == 'sent' and rec.date_required and rec.date_required < today
            end = rec.answer_date.date() if rec.answer_date else today
            rec.days_open = (end - rec.date_sent).days if rec.date_sent else 0

    def _search_overdue(self, operator, value):
        today = fields.Date.context_today(self)
        domain = [('state', '=', 'sent'), ('date_required', '<', today)]
        if operator == 'in':
            positive = any(value)
        elif operator == 'not in':
            positive = not any(value)
        else:
            positive = (operator in ('=', '==') and value) or (operator == '!=' and not value)
        return domain if positive else ['!', '&'] + domain

    def action_send(self):
        today = fields.Date.context_today(self)
        for rec in self:
            if rec.state != 'draft':
                continue
            rec.write({
                'state': 'sent', 'date_sent': today,
                'date_required': rec.date_required or today + timedelta(days=rec.company_id.dvz_rfi_days or 7),
            })
        self._dvz_notify(_('A request for information is waiting for your answer.'), _('Answer the RFI'))
        return True

    def _dvz_answer(self, partner, answer, attachments=None):
        self.ensure_one()
        if self.state != 'sent':
            raise UserError(_('%s is not waiting for an answer.', self.name))
        if not (answer or '').strip():
            raise UserError(_('Please write the answer.'))
        vals = {'answer': answer, 'answered_by_id': partner.id, 'answer_date': fields.Datetime.now(),
                'state': 'answered'}
        if attachments:
            vals['answer_attachment_ids'] = [(4, a.id) for a in attachments]
        self.write(vals)
        self.message_post(body=Markup('<p><b>%s</b></p><p>%s</p>') % (_('Answered by %s', partner.name), answer),
                          author_id=partner.id, message_type='comment', subtype_xmlid='mail.mt_comment')
        if self.user_id:
            self.activity_schedule('mail.mail_activity_data_todo', user_id=self.user_id.id,
                                   summary=_('RFI %s answered', self.name))
        return True

    def action_mark_answered(self):
        """Answer received outside the portal (letter, email): record it here."""
        for rec in self:
            if not rec.answer:
                raise UserError(_('Type the answer you received first.'))
            rec._dvz_answer(rec.contract_id.consultant_ids[:1] or rec.partner_id, rec.answer)
        return True

    def action_close(self):
        self.filtered(lambda r: r.state in ('answered', 'sent')).write({'state': 'closed'})
        return True

    def action_cancel(self):
        self.write({'state': 'cancel'})
        return True

    def action_draft(self):
        self.filtered(lambda r: r.state == 'cancel').write({'state': 'draft'})
        return True

    def action_create_variation(self):
        self.ensure_one()
        if self.variation_id:
            return self._open_variation()
        if self.contract_id.state not in ('progress', 'handover'):
            raise UserError(_('Variation orders need a confirmed contract.'))
        variation = self.env['dvz.contract.variation'].create({
            'title': self.subject,
            'contract_id': self.contract_id.id,
            'reason': 'design_change' if self.discipline != 'other' else 'other',
            'instruction_ref': self.name,
            'time_extension_days': self.impact_days if self.time_impact else 0,
            'description': Markup('<p><b>%s</b></p><p>%s</p><p><b>%s</b></p><p>%s</p>') % (
                _('Question'), self.question or '', _('Answer'), self.answer or ''),
        })
        self.variation_id = variation
        self.message_post(body=_('Variation order %s created from this RFI.', variation.name))
        return self._open_variation()

    def _open_variation(self):
        return {'type': 'ir.actions.act_window', 'res_model': 'dvz.contract.variation',
                'res_id': self.variation_id.id, 'view_mode': 'form'}

    @api.model
    def _cron_remind_overdue(self):
        for rec in self.search([('is_overdue', '=', True)]):
            if rec.user_id and not rec.activity_ids.filtered(lambda a: a.summary and 'overdue' in a.summary):
                rec.activity_schedule('mail.mail_activity_data_todo', user_id=rec.user_id.id,
                                      summary=_('RFI %s is overdue: chase the consultant', rec.name))
