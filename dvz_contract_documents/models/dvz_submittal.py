from datetime import timedelta

from markupsafe import Markup

from odoo import _, api, fields, models
from odoo.exceptions import UserError

REVIEW_CODES = [
    ('A', 'A - Approved'),
    ('B', 'B - Approved as noted'),
    ('C', 'C - Revise and resubmit'),
    ('D', 'D - Rejected'),
]


class DvzSubmittal(models.Model):
    _name = 'dvz.submittal'
    _description = 'Submittal (Material / Shop Drawing / Method Statement)'
    _inherit = ['dvz.doc.mixin']
    _order = 'id desc'
    _dvz_sequence = 'dvz.submittal'
    _dvz_portal_prefix = 'submittal'

    title = fields.Char('Title', required=True, tracking=True)
    submittal_type = fields.Selection([
        ('material', 'Material approval'), ('shop_drawing', 'Shop drawing'), ('method', 'Method statement'),
        ('sample', 'Sample / mock-up'), ('itp', 'Inspection & test plan'), ('as_built', 'As-built drawing'),
        ('other', 'Other'),
    ], 'Type', required=True, default='material', tracking=True)
    spec_section = fields.Char('Specification Section')
    contract_line_id = fields.Many2one('dvz.contract.line', 'BOQ Item',
                                       domain="[('contract_id', '=', contract_id), ('display_type', '=', False)]")
    revision = fields.Integer('Revision', default=0, copy=False, readonly=True)
    revision_label = fields.Char('Rev.', compute='_compute_revision_label')
    parent_id = fields.Many2one('dvz.submittal', 'Previous Revision', readonly=True, copy=False, index='btree_not_null')
    child_ids = fields.One2many('dvz.submittal', 'parent_id', 'Next Revisions')
    description = fields.Text('Description')
    state = fields.Selection([
        ('draft', 'Draft'), ('submitted', 'Under review'), ('reviewed', 'Reviewed'), ('closed', 'Closed'),
        ('superseded', 'Superseded'), ('cancel', 'Cancelled'),
    ], default='draft', required=True, tracking=True, copy=False, index=True)
    date_submitted = fields.Date('Submitted On', readonly=True, copy=False)
    date_due = fields.Date('Review Due', tracking=True, copy=False)
    review_code = fields.Selection(REVIEW_CODES, 'Review Code', tracking=True, copy=False)
    review_comment = fields.Text('Reviewer Comments', copy=False)
    reviewed_by_id = fields.Many2one('res.partner', 'Reviewed By', readonly=True, copy=False)
    review_date = fields.Datetime('Reviewed On', readonly=True, copy=False)
    review_attachment_ids = fields.Many2many('ir.attachment', 'dvz_submittal_review_attachment_rel', 'submittal_id',
                                             'attachment_id', string='Marked-up Documents', copy=False)
    is_overdue = fields.Boolean('Overdue', compute='_compute_overdue', search='_search_overdue')

    @api.depends('revision')
    def _compute_revision_label(self):
        for rec in self:
            rec.revision_label = 'R%s' % rec.revision

    @api.depends('state', 'date_due')
    def _compute_overdue(self):
        today = fields.Date.context_today(self)
        for rec in self:
            rec.is_overdue = rec.state == 'submitted' and rec.date_due and rec.date_due < today

    def _search_overdue(self, operator, value):
        today = fields.Date.context_today(self)
        domain = [('state', '=', 'submitted'), ('date_due', '<', today)]
        if operator == 'in':
            positive = any(value)
        elif operator == 'not in':
            positive = not any(value)
        else:
            positive = (operator in ('=', '==') and value) or (operator == '!=' and not value)
        return domain if positive else ['!', '&'] + domain

    @api.depends('name', 'revision', 'title')
    def _compute_display_name(self):
        for rec in self:
            rec.display_name = '%s R%s %s' % (rec.name or '', rec.revision, rec.title or '')

    def action_submit(self):
        today = fields.Date.context_today(self)
        for rec in self:
            if rec.state != 'draft':
                continue
            if not rec.attachment_ids:
                raise UserError(_('Attach the documents to review (datasheet, drawing, method statement) before submitting %s.', rec.name))
            rec.write({'state': 'submitted', 'date_submitted': today,
                       'date_due': rec.date_due or today + timedelta(days=rec.company_id.dvz_submittal_days or 14)})
        self._dvz_notify(_('A submittal is waiting for your review.'), _('Review the submittal'))
        return True

    def _dvz_review(self, partner, code, comment, attachments=None):
        self.ensure_one()
        if self.state != 'submitted':
            raise UserError(_('%s is not under review.', self.display_name))
        if code not in dict(REVIEW_CODES):
            raise UserError(_('Choose a review code (A, B, C or D).'))
        if code in ('B', 'C', 'D') and not (comment or '').strip():
            raise UserError(_('Please add your comments for code %s.', code))
        vals = {'review_code': code, 'review_comment': comment or False, 'reviewed_by_id': partner.id,
                'review_date': fields.Datetime.now(), 'state': 'reviewed'}
        if attachments:
            vals['review_attachment_ids'] = [(4, a.id) for a in attachments]
        self.write(vals)
        body = Markup('<p><b>%s</b></p>') % _('Reviewed by %(name)s: %(code)s', name=partner.name,
                                              code=dict(REVIEW_CODES)[code])
        if comment:
            body += Markup('<p>%s</p>') % comment
        self.message_post(body=body, author_id=partner.id, message_type='comment', subtype_xmlid='mail.mt_comment')
        if self.user_id:
            self.activity_schedule('mail.mail_activity_data_todo', user_id=self.user_id.id,
                                   summary=_('%(doc)s reviewed: code %(code)s', doc=self.name, code=code))
        return True

    def action_record_review(self):
        """Review received outside the portal: fill code and comments, then press this."""
        for rec in self:
            rec._dvz_review(rec.contract_id.consultant_ids[:1] or rec.partner_id, rec.review_code, rec.review_comment)
        return True

    def action_resubmit(self):
        """New revision (R+1) after code B, C or D. The old revision is kept as superseded."""
        self.ensure_one()
        if self.state != 'reviewed' or self.review_code == 'A':
            raise UserError(_('Only submittals reviewed with code B, C or D need a new revision.'))
        new = self.copy({'revision': self.revision + 1, 'parent_id': self.id, 'name': self.name})
        self.state = 'superseded'
        return {'type': 'ir.actions.act_window', 'res_model': self._name, 'res_id': new.id, 'view_mode': 'form'}

    def action_close(self):
        for rec in self:
            if rec.state != 'reviewed' or rec.review_code not in ('A', 'B'):
                raise UserError(_('Close submittals approved with code A or B. For C or D, create a new revision.'))
        self.write({'state': 'closed'})
        return True

    def action_cancel(self):
        self.write({'state': 'cancel'})
        return True

    def action_draft(self):
        self.filtered(lambda r: r.state == 'cancel').write({'state': 'draft'})
        return True

    @api.model
    def _cron_remind_overdue(self):
        for rec in self.search([('is_overdue', '=', True)]):
            if rec.user_id and not rec.activity_ids.filtered(lambda a: a.summary and 'overdue' in a.summary):
                rec.activity_schedule('mail.mail_activity_data_todo', user_id=rec.user_id.id,
                                      summary=_('Submittal %s review is overdue: chase the consultant', rec.name))
