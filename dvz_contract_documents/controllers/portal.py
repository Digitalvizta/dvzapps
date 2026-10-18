import base64
from urllib.parse import quote

from odoo import http
from odoo.exceptions import UserError
from odoo.http import request

from odoo.addons.dvz_contract_portal.controllers.portal import DvzContractPortal

MAX_UPLOAD = 25 * 1024 * 1024


class DvzDocumentsPortal(DvzContractPortal):

    # ------------------------------------------------------------------ access
    def _dvz_doc_get(self, model, record_id):
        record = request.env[model].sudo().browse(int(record_id)).exists()
        if not record or record.state in ('draft', 'cancel'):
            return None
        partner = self._dvz_partner()
        if model == 'dvz.transmittal' and record.to_partner_id.commercial_partner_id == partner.commercial_partner_id:
            return record
        if record.contract_id in self._dvz_contracts():
            return record
        return None

    def _dvz_waiting_docs(self):
        partner = self._dvz_partner()
        contracts = self._dvz_contracts().filtered(lambda c: partner in c.consultant_ids)
        env = request.env
        rfis = env['dvz.rfi'].sudo().search([('contract_id', 'in', contracts.ids), ('state', '=', 'sent')])
        subs = env['dvz.submittal'].sudo().search([('contract_id', 'in', contracts.ids), ('state', '=', 'submitted')])
        trans = env['dvz.transmittal'].sudo().search([
            ('state', '=', 'sent'), ('to_partner_id', 'child_of', partner.commercial_partner_id.id)])
        return rfis, subs, trans

    def _prepare_home_portal_values(self, counters):
        values = super()._prepare_home_portal_values(counters)
        if 'dvz_doc_count' in counters:
            rfis, subs, trans = self._dvz_waiting_docs()
            values['dvz_doc_count'] = len(rfis) + len(subs) + len(trans)
        return values

    def _dvz_upload(self, record):
        files = request.httprequest.files.getlist('files')
        attachments = request.env['ir.attachment']
        for f in files:
            if not f or not f.filename:
                continue
            data = f.read()
            if len(data) > MAX_UPLOAD:
                raise UserError('%s is larger than 25 MB.' % f.filename)
            attachments |= request.env['ir.attachment'].sudo().create({
                'name': f.filename, 'datas': base64.b64encode(data), 'res_model': record._name, 'res_id': record.id,
            })
        return attachments

    def _dvz_doc_values(self, record, page, **extra):
        values = self._prepare_portal_layout_values()
        values.update({'doc': record, 'contract': record.contract_id, 'page_name': page,
                       'is_consultant': record.contract_id._dvz_portal_is_consultant(self._dvz_partner())})
        values.update(extra)
        return values

    # ------------------------------------------------------------------ pages
    @http.route('/my/contracting/documents', type='http', auth='user', website=True)
    def dvz_portal_documents(self, **kw):
        rfis, subs, trans = self._dvz_waiting_docs()
        contracts = self._dvz_contracts()
        env = request.env
        values = self._prepare_portal_layout_values()
        values.update({
            'rfis': rfis, 'submittals': subs, 'transmittals': trans,
            'all_rfis': env['dvz.rfi'].sudo().search([('contract_id', 'in', contracts.ids),
                                                       ('state', 'not in', ('draft', 'cancel'))], limit=200),
            'all_submittals': env['dvz.submittal'].sudo().search([('contract_id', 'in', contracts.ids),
                                                                   ('state', 'not in', ('draft', 'cancel'))], limit=200),
            'page_name': 'dvz_documents',
        })
        return request.render('dvz_contract_documents.portal_my_dvz_documents', values)

    @http.route('/my/contracting/rfi/<int:rfi_id>', type='http', auth='user', website=True)
    def dvz_portal_rfi(self, rfi_id, message=None, error=None, **kw):
        rfi = self._dvz_doc_get('dvz.rfi', rfi_id)
        if not rfi:
            return request.redirect('/my/contracting/documents')
        values = self._dvz_doc_values(rfi, 'dvz_rfi', message=message, error=error,
                                      files=rfi._dvz_portal_files(), answer_files=rfi._dvz_portal_files('answer_attachment_ids'))
        values['can_answer'] = rfi.state == 'sent' and values['is_consultant']
        return request.render('dvz_contract_documents.portal_my_dvz_rfi', values)

    @http.route('/my/contracting/rfi/<int:rfi_id>/answer', type='http', auth='user', methods=['POST'], website=True)
    def dvz_portal_rfi_answer(self, rfi_id, answer=None, **kw):
        path = '/my/contracting/rfi/%s' % rfi_id
        rfi = self._dvz_doc_get('dvz.rfi', rfi_id)
        if not rfi:
            return request.redirect('/my/contracting/documents')
        try:
            if not rfi.contract_id._dvz_portal_is_consultant(self._dvz_partner()):
                raise UserError('Only the consultants of this contract can answer RFIs.')
            rfi._dvz_answer(self._dvz_partner(), answer, self._dvz_upload(rfi))
        except UserError as e:
            return request.redirect('%s?error=%s' % (path, quote(str(e.args[0]))))
        return request.redirect('%s?message=answered' % path)

    @http.route('/my/contracting/submittal/<int:sub_id>', type='http', auth='user', website=True)
    def dvz_portal_submittal(self, sub_id, message=None, error=None, **kw):
        sub = self._dvz_doc_get('dvz.submittal', sub_id)
        if not sub:
            return request.redirect('/my/contracting/documents')
        values = self._dvz_doc_values(sub, 'dvz_submittal', message=message, error=error,
                                      files=sub._dvz_portal_files(), review_files=sub._dvz_portal_files('review_attachment_ids'),
                                      codes=sub._fields['review_code'].selection)
        values['can_review'] = sub.state == 'submitted' and values['is_consultant']
        return request.render('dvz_contract_documents.portal_my_dvz_submittal', values)

    @http.route('/my/contracting/submittal/<int:sub_id>/review', type='http', auth='user', methods=['POST'], website=True)
    def dvz_portal_submittal_review(self, sub_id, code=None, comment=None, **kw):
        path = '/my/contracting/submittal/%s' % sub_id
        sub = self._dvz_doc_get('dvz.submittal', sub_id)
        if not sub:
            return request.redirect('/my/contracting/documents')
        try:
            if not sub.contract_id._dvz_portal_is_consultant(self._dvz_partner()):
                raise UserError('Only the consultants of this contract can review submittals.')
            sub._dvz_review(self._dvz_partner(), code, comment, self._dvz_upload(sub))
        except UserError as e:
            return request.redirect('%s?error=%s' % (path, quote(str(e.args[0]))))
        return request.redirect('%s?message=reviewed' % path)

    @http.route('/my/contracting/transmittal/<int:tr_id>', type='http', auth='user', website=True)
    def dvz_portal_transmittal(self, tr_id, message=None, error=None, **kw):
        tr = self._dvz_doc_get('dvz.transmittal', tr_id)
        if not tr:
            return request.redirect('/my/contracting/documents')
        partner = self._dvz_partner()
        values = self._dvz_doc_values(tr, 'dvz_transmittal', message=message, error=error, files=tr._dvz_portal_files())
        values['can_ack'] = tr.state == 'sent' and \
            tr.to_partner_id.commercial_partner_id == partner.commercial_partner_id
        return request.render('dvz_contract_documents.portal_my_dvz_transmittal', values)

    @http.route('/my/contracting/transmittal/<int:tr_id>/ack', type='http', auth='user', methods=['POST'], website=True)
    def dvz_portal_transmittal_ack(self, tr_id, **kw):
        path = '/my/contracting/transmittal/%s' % tr_id
        tr = self._dvz_doc_get('dvz.transmittal', tr_id)
        if not tr:
            return request.redirect('/my/contracting/documents')
        partner = self._dvz_partner()
        try:
            if tr.to_partner_id.commercial_partner_id != partner.commercial_partner_id:
                raise UserError('Only the receiver can acknowledge this transmittal.')
            tr._dvz_acknowledge(partner)
        except UserError as e:
            return request.redirect('%s?error=%s' % (path, quote(str(e.args[0]))))
        return request.redirect('%s?message=acknowledged' % path)

    @http.route('/my/contracting/contract/<int:contract_id>', type='http', auth='user', website=True)
    def dvz_portal_contract(self, contract_id, **kw):
        # same page as before, plus the contract's RFIs and submittals
        response = super().dvz_portal_contract(contract_id, **kw)
        if hasattr(response, 'qcontext') and response.qcontext.get('contract'):
            contract = response.qcontext['contract']
            response.qcontext['dvz_rfis'] = contract.rfi_ids.filtered(lambda r: r.state not in ('draft', 'cancel'))
            response.qcontext['dvz_submittals'] = contract.submittal_ids.filtered(
                lambda s: s.state not in ('draft', 'cancel', 'superseded'))
        return response
