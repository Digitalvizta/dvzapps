from urllib.parse import quote

from odoo import http
from odoo.exceptions import UserError
from odoo.http import request

from odoo.addons.portal.controllers.portal import CustomerPortal, pager as portal_pager


class DvzContractPortal(CustomerPortal):

    # ------------------------------------------------------------------
    # helpers
    # ------------------------------------------------------------------
    def _dvz_partner(self):
        return request.env.user.partner_id

    def _dvz_contracts(self):
        partner = self._dvz_partner()
        Contract = request.env['dvz.contract'].sudo()
        return Contract.search(Contract._dvz_portal_domain(partner))

    def _dvz_pending(self):
        partner = self._dvz_partner()
        contracts = self._dvz_contracts().filtered(lambda c: partner in c.consultant_ids)
        certs = request.env['dvz.contract.certificate'].sudo().search(
            [('contract_id', 'in', contracts.ids), ('state', '=', 'submitted')])
        variations = request.env['dvz.contract.variation'].sudo().search(
            [('contract_id', 'in', contracts.ids), ('state', '=', 'submitted')])
        return certs, variations

    def _dvz_get(self, model, record_id):
        record = request.env[model].sudo().browse(int(record_id)).exists()
        if not record:
            return None
        contract = record if model == 'dvz.contract' else record.contract_id
        if contract not in self._dvz_contracts():
            return None
        return record

    def _prepare_home_portal_values(self, counters):
        values = super()._prepare_home_portal_values(counters)
        if 'dvz_contract_count' in counters:
            values['dvz_contract_count'] = len(self._dvz_contracts())
        if 'dvz_approval_count' in counters:
            certs, variations = self._dvz_pending()
            values['dvz_approval_count'] = len(certs) + len(variations)
        return values

    # ------------------------------------------------------------------
    # pages
    # ------------------------------------------------------------------
    @http.route(['/my/contracting', '/my/contracting/page/<int:page>'], type='http', auth='user', website=True)
    def dvz_portal_contracts(self, page=1, **kw):
        contracts = self._dvz_contracts()
        pager = portal_pager(url='/my/contracting', total=len(contracts), page=page, step=20)
        values = self._prepare_portal_layout_values()
        values.update({
            'contracts': contracts[pager['offset']:pager['offset'] + 20],
            'pager': pager,
            'page_name': 'dvz_contracts',
            'partner': self._dvz_partner(),
        })
        return request.render('dvz_contract_portal.portal_my_dvz_contracts', values)

    @http.route('/my/contracting/approvals', type='http', auth='user', website=True)
    def dvz_portal_approvals(self, **kw):
        certs, variations = self._dvz_pending()
        values = self._prepare_portal_layout_values()
        values.update({'certificates': certs, 'variations': variations, 'page_name': 'dvz_approvals'})
        return request.render('dvz_contract_portal.portal_my_dvz_approvals', values)

    @http.route('/my/contracting/contract/<int:contract_id>', type='http', auth='user', website=True)
    def dvz_portal_contract(self, contract_id, **kw):
        contract = self._dvz_get('dvz.contract', contract_id)
        if not contract:
            return request.redirect('/my/contracting')
        values = self._prepare_portal_layout_values()
        values.update({
            'contract': contract,
            'certificates': contract.certificate_ids.filtered(lambda c: c.state != 'draft').sorted('date', reverse=True),
            'variations': contract.variation_ids.filtered(lambda v: v.state != 'draft').sorted('date', reverse=True)
            if 'variation_ids' in contract._fields else [],
            'is_consultant': contract._dvz_portal_is_consultant(self._dvz_partner()),
            'page_name': 'dvz_contract',
        })
        return request.render('dvz_contract_portal.portal_my_dvz_contract', values)

    @http.route('/my/contracting/certificate/<int:cert_id>', type='http', auth='user', website=True)
    def dvz_portal_certificate(self, cert_id, message=None, error=None, **kw):
        cert = self._dvz_get('dvz.contract.certificate', cert_id)
        if not cert or cert.state == 'draft' and not cert.portal_decision:
            return request.redirect('/my/contracting')
        values = self._prepare_portal_layout_values()
        values.update({
            'cert': cert,
            'contract': cert.contract_id,
            'lines': cert.line_ids.filtered(lambda l: l.display_type or l.qty_current or l.qty_previous),
            'can_decide': cert.state == 'submitted' and cert.contract_id._dvz_portal_is_consultant(self._dvz_partner()),
            'message': message,
            'error': error,
            'page_name': 'dvz_certificate',
        })
        return request.render('dvz_contract_portal.portal_my_dvz_certificate', values)

    @http.route('/my/contracting/variation/<int:variation_id>', type='http', auth='user', website=True)
    def dvz_portal_variation(self, variation_id, message=None, error=None, **kw):
        variation = self._dvz_get('dvz.contract.variation', variation_id)
        if not variation or variation.state == 'draft' and not variation.portal_decision:
            return request.redirect('/my/contracting')
        values = self._prepare_portal_layout_values()
        values.update({
            'variation': variation,
            'contract': variation.contract_id,
            'can_decide': variation.state == 'submitted'
            and variation.contract_id._dvz_portal_is_consultant(self._dvz_partner()),
            'message': message,
            'error': error,
            'page_name': 'dvz_variation',
        })
        return request.render('dvz_contract_portal.portal_my_dvz_variation', values)

    # ------------------------------------------------------------------
    # decisions
    # ------------------------------------------------------------------
    def _dvz_decide(self, model, record_id, decision, comment, path):
        record = self._dvz_get(model, record_id)
        if not record:
            return request.redirect('/my/contracting')
        if decision not in ('approve', 'reject'):
            return request.redirect(path)
        try:
            record._dvz_portal_decide(self._dvz_partner(), decision, comment)
        except UserError as e:
            return request.redirect('%s?error=%s' % (path, quote(str(e.args[0]))))
        message = 'approved' if decision == 'approve' else 'rejected'
        return request.redirect('%s?message=%s' % (path, message))

    @http.route('/my/contracting/certificate/<int:cert_id>/decide', type='http', auth='user', methods=['POST'],
                website=True)
    def dvz_portal_certificate_decide(self, cert_id, decision=None, comment=None, **kw):
        return self._dvz_decide('dvz.contract.certificate', cert_id, decision, comment,
                                '/my/contracting/certificate/%s' % cert_id)

    @http.route('/my/contracting/variation/<int:variation_id>/decide', type='http', auth='user', methods=['POST'],
                website=True)
    def dvz_portal_variation_decide(self, variation_id, decision=None, comment=None, **kw):
        return self._dvz_decide('dvz.contract.variation', variation_id, decision, comment,
                                '/my/contracting/variation/%s' % variation_id)
