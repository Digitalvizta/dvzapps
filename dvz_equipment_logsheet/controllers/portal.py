from odoo import _, http
from odoo.exceptions import AccessError, MissingError, UserError
from odoo.http import request

from odoo.addons.portal.controllers.portal import CustomerPortal, pager as portal_pager


class EquipmentLogsheetPortal(CustomerPortal):

    def _prepare_home_portal_values(self, counters):
        values = super()._prepare_home_portal_values(counters)
        if 'equipment_logsheet_count' in counters:
            Sheet = request.env['dvz.equipment.logsheet']
            values['equipment_logsheet_count'] = (
                Sheet.search_count([('state', '!=', 'draft')]) if Sheet.has_access('read') else 0)
        return values

    @http.route(['/my/equipment/logsheets', '/my/equipment/logsheets/page/<int:page>'],
                type='http', auth='user', website=True)
    def portal_my_equipment_logsheets(self, page=1, **kw):
        Sheet = request.env['dvz.equipment.logsheet']
        domain = [('state', '!=', 'draft')]
        total = Sheet.search_count(domain)
        pager = portal_pager(url='/my/equipment/logsheets', total=total, page=page, step=self._items_per_page)
        sheets = Sheet.search(domain, order='date_from desc, id desc',
                              limit=self._items_per_page, offset=pager['offset']).sudo()
        values = self._prepare_portal_layout_values()
        values.update({
            'sheets': sheets,
            'page_name': 'equipment_logsheet',
            'pager': pager,
            'default_url': '/my/equipment/logsheets',
        })
        return request.render('dvz_equipment_logsheet.portal_my_equipment_logsheets', values)

    @http.route(['/my/equipment/logsheets/<int:sheet_id>'], type='http', auth='public', website=True)
    def portal_my_equipment_logsheet(self, sheet_id, access_token=None, message=None, **kw):
        try:
            sheet_sudo = self._document_check_access('dvz.equipment.logsheet', sheet_id, access_token)
        except (AccessError, MissingError):
            return request.redirect('/my')
        values = self._get_page_view_values(
            sheet_sudo, access_token, {'sheet': sheet_sudo, 'page_name': 'equipment_logsheet', 'message': message},
            'my_equipment_logsheets_history', False)
        return request.render('dvz_equipment_logsheet.portal_my_equipment_logsheet', values)

    @http.route(['/my/equipment/logsheets/<int:sheet_id>/decision'], type='http', auth='public',
                methods=['POST'], website=True)
    def portal_equipment_logsheet_decision(self, sheet_id, access_token=None, decision=None, reason=None, **kw):
        try:
            sheet_sudo = self._document_check_access('dvz.equipment.logsheet', sheet_id, access_token)
        except (AccessError, MissingError):
            return request.redirect('/my')
        user = request.env.user
        by_name = user.name if not user._is_public() else (sheet_sudo.partner_id.name or _('Client'))
        message = 'done'
        if decision != 'approve' and not (reason or '').strip():
            message = 'reason'
        else:
            try:
                sheet_sudo._portal_set_decision(decision == 'approve', by_name, reason)
            except UserError:
                message = 'error'
        url = sheet_sudo.get_portal_url(query_string='&message=%s' % message)
        return request.redirect(url)
