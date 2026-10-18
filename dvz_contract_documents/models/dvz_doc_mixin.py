from markupsafe import Markup

from odoo import _, api, fields, models


class DvzDocMixin(models.AbstractModel):
    """Shared by RFIs, submittals and transmittals: contract, number, attachments, portal link, notifications."""
    _name = 'dvz.doc.mixin'
    _description = 'Contract document'
    _inherit = ['mail.thread', 'mail.activity.mixin']
    _check_company_auto = True
    _dvz_sequence = False
    _dvz_portal_prefix = False

    name = fields.Char('Number', required=True, copy=False, readonly=True, default=lambda self: _('New'), index='trigram')
    contract_id = fields.Many2one(
        'dvz.contract', 'Contract', required=True, index=True, tracking=True, check_company=True,
        domain="[('contract_type', '=', 'client'), ('state', 'in', ('draft', 'progress', 'handover'))]")
    partner_id = fields.Many2one(related='contract_id.partner_id', store=True, string='Client')
    project_id = fields.Many2one(related='contract_id.project_id', store=True)
    company_id = fields.Many2one(related='contract_id.company_id', store=True, index=True)
    user_id = fields.Many2one('res.users', 'Responsible', default=lambda self: self.env.user, tracking=True)
    attachment_ids = fields.Many2many('ir.attachment', string='Documents', copy=False,
                                      help='Drawings, specifications and photos sent with this document.')

    @api.model_create_multi
    def create(self, vals_list):
        for vals in vals_list:
            if vals.get('name', _('New')) == _('New') and self._dvz_sequence:
                vals['name'] = self.env['ir.sequence'].next_by_code(self._dvz_sequence) or _('New')
        records = super().create(vals_list)
        records._dvz_attach_files()
        return records

    def write(self, vals):
        res = super().write(vals)
        if any(f in vals for f in self._dvz_attachment_fields()):
            self._dvz_attach_files()
        return res

    def _dvz_attachment_fields(self):
        return [f for f in ('attachment_ids', 'answer_attachment_ids', 'review_attachment_ids') if f in self._fields]

    def _dvz_attach_files(self):
        """Uploaded files belong to the record, so portal users with access can download them."""
        for rec in self:
            for fname in rec._dvz_attachment_fields():
                rec[fname].filtered(lambda a: not a.res_id).sudo().write({'res_model': rec._name, 'res_id': rec.id})

    def get_dvz_portal_url(self):
        self.ensure_one()
        return '%s/my/contracting/%s/%s' % (self.get_base_url(), self._dvz_portal_prefix, self.id)

    def _dvz_recipients(self):
        return self.contract_id.consultant_ids

    def _dvz_notify(self, text, button):
        for rec in self:
            partners = rec._dvz_recipients()
            if not partners:
                continue
            rec.message_subscribe(partner_ids=partners.ids)
            body = Markup('<p>%s</p><p><a href="%s" class="btn btn-primary">%s</a></p>') % (
                text, rec.get_dvz_portal_url(), button)
            rec.message_post(body=body, partner_ids=partners.ids, message_type='comment',
                             subtype_xmlid='mail.mt_comment', attachment_ids=rec.attachment_ids.ids)

    def _dvz_portal_files(self, fname='attachment_ids'):
        """[(name, url)] with access tokens, for the portal pages."""
        files = []
        for att in self[fname].sudo():
            token = att.access_token or att.generate_access_token()[0]
            files.append((att.name, '/web/content/%s?download=true&access_token=%s' % (att.id, token)))
        return files
