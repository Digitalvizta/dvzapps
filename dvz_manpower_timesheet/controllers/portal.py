from odoo import _, http
from odoo.exceptions import AccessError, MissingError, UserError
from odoo.http import request

from odoo.addons.portal.controllers.portal import CustomerPortal, pager as portal_pager


class ManpowerTimesheetPortal(CustomerPortal):

    def _prepare_home_portal_values(self, counters):
        values = super()._prepare_home_portal_values(counters)
        if 'manpower_timesheet_count' in counters:
            Sheet = request.env['dvz.manpower.timesheet']
            values['manpower_timesheet_count'] = (
                Sheet.search_count([('state', '!=', 'draft')]) if Sheet.has_access('read') else 0)
        return values

    @http.route(['/my/manpower/timesheets', '/my/manpower/timesheets/page/<int:page>'],
                type='http', auth='user', website=True)
    def portal_my_manpower_timesheets(self, page=1, **kw):
        Sheet = request.env['dvz.manpower.timesheet']
        domain = [('state', '!=', 'draft')]
        total = Sheet.search_count(domain)
        pager = portal_pager(url='/my/manpower/timesheets', total=total, page=page, step=self._items_per_page)
        sheets = Sheet.search(domain, order='date_from desc, id desc',
                              limit=self._items_per_page, offset=pager['offset']).sudo()
        values = self._prepare_portal_layout_values()
        values.update({
            'sheets': sheets,
            'page_name': 'manpower_timesheet',
            'pager': pager,
            'default_url': '/my/manpower/timesheets',
        })
        return request.render('dvz_manpower_timesheet.portal_my_manpower_timesheets', values)

    @http.route(['/my/manpower/timesheets/<int:sheet_id>'], type='http', auth='public', website=True)
    def portal_my_manpower_timesheet(self, sheet_id, access_token=None, message=None, **kw):
        try:
            sheet_sudo = self._document_check_access('dvz.manpower.timesheet', sheet_id, access_token)
        except (AccessError, MissingError):
            return request.redirect('/my')
        values = self._get_page_view_values(
            sheet_sudo, access_token, {'sheet': sheet_sudo, 'page_name': 'manpower_timesheet', 'message': message},
            'my_manpower_timesheets_history', False)
        return request.render('dvz_manpower_timesheet.portal_my_manpower_timesheet', values)

    @http.route(['/my/manpower/timesheets/<int:sheet_id>/decision'], type='http', auth='public',
                methods=['POST'], website=True)
    def portal_manpower_timesheet_decision(self, sheet_id, access_token=None, decision=None, reason=None, **kw):
        try:
            sheet_sudo = self._document_check_access('dvz.manpower.timesheet', sheet_id, access_token)
        except (AccessError, MissingError):
            return request.redirect('/my')
        user = request.env.user
        by_name = user.name if not user._is_public() else (sheet_sudo.partner_id.name or _('Client'))
        message = 'done'
        try:
            sheet_sudo._portal_set_decision(decision == 'approve', by_name, reason)
        except UserError:
            message = 'error'
        url = sheet_sudo.get_portal_url(query_string='&message=%s' % message)
        return request.redirect(url)
