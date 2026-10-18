from markupsafe import Markup

from odoo import _, api, fields, models
from odoo.exceptions import UserError


class DvzTransmittal(models.Model):
    _name = 'dvz.transmittal'
    _description = 'Document Transmittal'
    _inherit = ['dvz.doc.mixin']
    _order = 'id desc'
    _dvz_sequence = 'dvz.transmittal'
    _dvz_portal_prefix = 'transmittal'

    to_partner_id = fields.Many2one('res.partner', 'To', required=True, tracking=True,
                                    help='Consultant, client or subcontractor receiving the documents.')
    subject = fields.Char('Subject', required=True)
    purpose = fields.Selection([
        ('approval', 'For approval'), ('review', 'For review & comments'), ('information', 'For information'),
        ('construction', 'For construction'), ('record', 'For record'),
    ], required=True, default='approval', tracking=True)
    date = fields.Date('Date', default=fields.Date.context_today, required=True)
    line_ids = fields.One2many('dvz.transmittal.line', 'transmittal_id', 'Document List', copy=True)
    message = fields.Text('Message')
    state = fields.Selection([('draft', 'Draft'), ('sent', 'Sent'), ('acknowledged', 'Acknowledged'),
                              ('cancel', 'Cancelled')], default='draft', required=True, tracking=True, copy=False)
    ack_partner_id = fields.Many2one('res.partner', 'Acknowledged By', readonly=True, copy=False)
    ack_date = fields.Datetime('Acknowledged On', readonly=True, copy=False)

    def _dvz_recipients(self):
        return self.to_partner_id

    def action_send(self):
        for rec in self:
            if rec.state != 'draft':
                continue
            if not (rec.line_ids or rec.attachment_ids):
                raise UserError(_('List the documents or attach files before sending %s.', rec.name))
            rec.state = 'sent'
        self._dvz_notify(_('Documents have been sent to you. Please acknowledge receipt.'), _('View and acknowledge'))
        return True

    def _dvz_acknowledge(self, partner):
        self.ensure_one()
        if self.state != 'sent':
            raise UserError(_('%s is not waiting for acknowledgement.', self.name))
        self.write({'state': 'acknowledged', 'ack_partner_id': partner.id, 'ack_date': fields.Datetime.now()})
        self.message_post(body=Markup('<p>%s</p>') % _('Receipt acknowledged by %s.', partner.name),
                          author_id=partner.id, message_type='comment', subtype_xmlid='mail.mt_note')
        return True

    def action_mark_acknowledged(self):
        for rec in self:
            rec._dvz_acknowledge(rec.to_partner_id)
        return True

    def action_cancel(self):
        self.write({'state': 'cancel'})
        return True

    def action_draft(self):
        self.filtered(lambda r: r.state == 'cancel').write({'state': 'draft'})
        return True


class DvzTransmittalLine(models.Model):
    _name = 'dvz.transmittal.line'
    _description = 'Transmittal Document'
    _order = 'sequence, id'

    transmittal_id = fields.Many2one('dvz.transmittal', required=True, ondelete='cascade', index=True)
    contract_id = fields.Many2one(related='transmittal_id.contract_id')
    sequence = fields.Integer(default=10)
    doc_ref = fields.Char('Document No.', required=True)
    description = fields.Char('Description', required=True)
    revision = fields.Char('Rev.')
    copies = fields.Integer('Copies', default=1)
    doc_format = fields.Selection([('pdf', 'PDF'), ('dwg', 'DWG'), ('hard', 'Hard copy'), ('sample', 'Sample')],
                                  'Format', default='pdf')
    submittal_id = fields.Many2one('dvz.submittal', 'Submittal', domain="[('contract_id', '=', contract_id)]")

    @api.onchange('submittal_id')
    def _onchange_submittal_id(self):
        if self.submittal_id:
            self.doc_ref = self.submittal_id.name
            self.description = self.submittal_id.title
            self.revision = self.submittal_id.revision_label
