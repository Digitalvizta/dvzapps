from markupsafe import Markup

from odoo import _, api, fields, models
from odoo.exceptions import UserError


class DvzContract(models.Model):
    _inherit = 'dvz.contract'

    consultant_ids = fields.Many2many(
        'res.partner', 'dvz_contract_consultant_rel', 'contract_id', 'partner_id', string='Consultants / Engineers',
        help='People who review and approve payment certificates and variation orders in the portal. '
             'Give them portal access from the contact form.')

    @api.model
    def _dvz_portal_domain(self, partner):
        commercial = partner.commercial_partner_id
        return [
            ('contract_type', '=', 'client'),
            ('state', 'in', ('progress', 'handover', 'closed')),
            '|', ('consultant_ids', 'in', partner.ids), ('partner_id', 'child_of', commercial.id),
        ]

    def _dvz_portal_is_consultant(self, partner):
        self.ensure_one()
        return partner in self.consultant_ids


class DvzPortalApprovalMixin(models.AbstractModel):
    _name = 'dvz.portal.approval.mixin'
    _description = 'Contracting portal approval'

    portal_decision = fields.Selection([('approved', 'Approved'), ('rejected', 'Rejected')],
                                       string='Consultant Decision', copy=False, readonly=True)
    portal_partner_id = fields.Many2one('res.partner', 'Decision By', copy=False, readonly=True)
    portal_decision_date = fields.Datetime('Decision On', copy=False, readonly=True)
    portal_comment = fields.Text('Consultant Comment', copy=False, readonly=True)

    def _dvz_portal_path(self):
        raise NotImplementedError

    def _dvz_portal_contract(self):
        return self.contract_id

    def get_dvz_portal_url(self):
        self.ensure_one()
        return '%s%s' % (self.get_base_url(), self._dvz_portal_path())

    def _dvz_portal_notify(self):
        for rec in self:
            consultants = rec._dvz_portal_contract().consultant_ids
            if not consultants:
                continue
            rec.message_subscribe(partner_ids=consultants.ids)
            url = rec.get_dvz_portal_url()
            body = Markup('<p>%s</p><p><a href="%s" class="btn btn-primary">%s</a></p>') % (
                _('%(doc)s is waiting for your review on contract %(contract)s.',
                  doc=rec.display_name, contract=rec._dvz_portal_contract().display_name),
                url, _('Review and approve'))
            rec.message_post(body=body, partner_ids=consultants.ids, message_type='comment',
                             subtype_xmlid='mail.mt_comment')

    def _dvz_portal_decide(self, partner, decision, comment):
        self.ensure_one()
        if self.state != 'submitted':
            raise UserError(_('%s is no longer waiting for approval.', self.display_name))
        if not self._dvz_portal_contract()._dvz_portal_is_consultant(partner):
            raise UserError(_('Only the consultants of this contract can approve it.'))
        if decision == 'reject' and not (comment or '').strip():
            raise UserError(_('Please write the reason for rejecting.'))
        self.write({
            'portal_decision': 'approved' if decision == 'approve' else 'rejected',
            'portal_partner_id': partner.id,
            'portal_decision_date': fields.Datetime.now(),
            'portal_comment': comment or False,
        })
        if decision == 'approve':
            self._do_approve()
            text = _('Approved in the portal by %s.', partner.name)
        else:
            self._dvz_portal_reject()
            text = _('Rejected in the portal by %s.', partner.name)
        body = Markup('<p><b>%s</b></p>') % text
        if comment:
            body += Markup('<p>%s</p>') % comment
        self.message_post(body=body, author_id=partner.id, message_type='comment', subtype_xmlid='mail.mt_comment')
        manager = self._dvz_portal_contract().user_id
        if manager:
            self.activity_schedule('mail.mail_activity_data_todo', user_id=manager.id,
                                   summary=text)
        return True


class DvzContractCertificate(models.Model):
    _name = 'dvz.contract.certificate'
    _inherit = ['dvz.contract.certificate', 'dvz.portal.approval.mixin']

    def _dvz_portal_path(self):
        return '/my/contracting/certificate/%s' % self.id

    def _dvz_portal_reject(self):
        self.write({'state': 'draft'})
        self.activity_unlink(['mail.mail_activity_data_todo'])

    def action_submit(self):
        res = super().action_submit()
        submitted = self.filtered(lambda c: c.state == 'submitted' and c.contract_type == 'client')
        submitted.filtered('portal_decision').write({'portal_decision': False})
        submitted._dvz_portal_notify()
        return res

    def action_draft(self):
        res = super().action_draft()
        self.filtered(lambda c: c.state == 'draft').write({'portal_decision': False})
        return res


class DvzContractVariation(models.Model):
    _name = 'dvz.contract.variation'
    _inherit = ['dvz.contract.variation', 'dvz.portal.approval.mixin']

    def _dvz_portal_path(self):
        return '/my/contracting/variation/%s' % self.id

    def _dvz_portal_reject(self):
        self.action_reject()

    def action_submit(self):
        res = super().action_submit()
        submitted = self.filtered(lambda v: v.state == 'submitted')
        submitted.filtered('portal_decision').write({'portal_decision': False})
        submitted._dvz_portal_notify()
        return res
