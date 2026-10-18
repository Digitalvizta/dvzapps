import base64

from odoo import Command, fields
from odoo.exceptions import UserError
from odoo.http import Request
from odoo.tests import HttpCase, TransactionCase, tagged


@tagged('post_install', '-at_install')
class TestDocuments(TransactionCase):

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.client = cls.env['res.partner'].create({'name': 'Owner Co'})
        cls.consultant = cls.env['res.partner'].create({'name': 'Engineer Partners', 'email': 'eng@example.com'})
        cls.contract = cls.env['dvz.contract'].create({
            'title': 'Hospital wing', 'partner_id': cls.client.id,
            'consultant_ids': [Command.set([cls.consultant.id])],
            'line_ids': [Command.create({'name': 'Concrete', 'quantity': 10, 'price_unit': 100})],
        })
        cls.contract.action_confirm()
        cls.file = cls.env['ir.attachment'].create({'name': 'drawing.pdf', 'datas': base64.b64encode(b'%PDF-1.4')})

    def test_01_rfi_flow_and_variation(self):
        rfi = self.env['dvz.rfi'].create({'contract_id': self.contract.id, 'subject': 'Slab thickness',
                                          'question': '200 or 250 mm at grid C?',
                                          'attachment_ids': [Command.set(self.file.ids)]})
        self.assertTrue(rfi.name.startswith('RFI-'))
        self.assertEqual(self.file.res_id, rfi.id, 'Uploaded file belongs to the RFI')
        rfi.action_send()
        self.assertEqual(rfi.state, 'sent')
        self.assertEqual(rfi.date_required, fields.Date.add(fields.Date.today(), days=7))
        self.assertIn(self.consultant, rfi.message_partner_ids)
        with self.assertRaises(UserError):
            rfi._dvz_answer(self.consultant, '   ')
        rfi._dvz_answer(self.consultant, '250 mm, see revised drawing S-104')
        self.assertEqual(rfi.state, 'answered')
        self.assertEqual(rfi.answered_by_id, self.consultant)
        rfi.write({'cost_impact': True, 'time_impact': True, 'impact_days': 5})
        rfi.action_create_variation()
        self.assertTrue(rfi.variation_id)
        self.assertEqual(rfi.variation_id.contract_id, self.contract)
        self.assertEqual(rfi.variation_id.time_extension_days, 5)
        self.contract.invalidate_recordset()
        self.assertEqual(self.contract.rfi_open_count, 0)

    def test_02_overdue(self):
        rfi = self.env['dvz.rfi'].create({'contract_id': self.contract.id, 'subject': 'Door type', 'question': '?'})
        rfi.action_send()
        rfi.date_required = fields.Date.add(fields.Date.today(), days=-1)
        self.assertTrue(rfi.is_overdue)
        self.assertIn(rfi, self.env['dvz.rfi'].search([('is_overdue', '=', True)]))
        self.env['dvz.rfi']._cron_remind_overdue()
        self.assertTrue(rfi.activity_ids)

    def test_03_submittal_revisions(self):
        sub = self.env['dvz.submittal'].create({'contract_id': self.contract.id, 'title': 'Waterproofing membrane'})
        with self.assertRaises(UserError):
            sub.action_submit()         # no documents attached
        sub.attachment_ids = [Command.set(self.file.ids)]
        sub.action_submit()
        self.assertEqual(sub.state, 'submitted')
        with self.assertRaises(UserError):
            sub._dvz_review(self.consultant, 'C', '')   # comments required
        sub._dvz_review(self.consultant, 'C', 'Thickness below specification')
        self.assertEqual(sub.review_code, 'C')
        with self.assertRaises(UserError):
            sub.action_close()
        action = sub.action_resubmit()
        new = self.env['dvz.submittal'].browse(action['res_id'])
        self.assertEqual(new.revision, 1)
        self.assertEqual(new.name, sub.name)
        self.assertEqual(new.revision_label, 'R1')
        self.assertEqual(sub.state, 'superseded')
        new.attachment_ids = [Command.set(self.file.copy().ids)]
        new.action_submit()
        new._dvz_review(self.consultant, 'A', '')
        new.action_close()
        self.assertEqual(new.state, 'closed')

    def test_04_transmittal(self):
        tr = self.env['dvz.transmittal'].create({
            'contract_id': self.contract.id, 'to_partner_id': self.consultant.id, 'subject': 'Shop drawings',
            'line_ids': [Command.create({'doc_ref': 'SD-001', 'description': 'Rebar layout', 'revision': 'R0'})]})
        tr.action_send()
        self.assertEqual(tr.state, 'sent')
        tr._dvz_acknowledge(self.consultant)
        self.assertEqual(tr.state, 'acknowledged')
        html = self.env['ir.actions.report']._render_qweb_html('dvz_contract_documents.report_dvz_transmittal', tr.ids)[0]
        self.assertIn(b'Rebar layout', html)


@tagged('post_install', '-at_install')
class TestDocumentsPortal(HttpCase):

    def test_portal_answer_rfi(self):
        consultant_user = self.env['res.users'].create({
            'name': 'Portal Engineer', 'login': 'portal_eng', 'password': 'portal_eng_123',
            'email': 'pe@example.com', 'group_ids': [Command.set([self.env.ref('base.group_portal').id])]})
        client = self.env['res.partner'].create({'name': 'Owner'})
        contract = self.env['dvz.contract'].create({
            'title': 'Tower', 'partner_id': client.id,
            'consultant_ids': [Command.set([consultant_user.partner_id.id])],
            'line_ids': [Command.create({'name': 'Piles', 'quantity': 1, 'price_unit': 10})]})
        contract.action_confirm()
        rfi = self.env['dvz.rfi'].create({'contract_id': contract.id, 'subject': 'Pile depth', 'question': 'Depth?'})
        rfi.action_send()
        self.authenticate('portal_eng', 'portal_eng_123')
        page = self.url_open('/my/contracting/documents')
        self.assertEqual(page.status_code, 200)
        self.assertIn('Pile depth', page.text)
        page = self.url_open('/my/contracting/rfi/%s' % rfi.id)
        self.assertIn('Send answer', page.text)
        res = self.url_open('/my/contracting/rfi/%s/answer' % rfi.id,
                            data={'answer': '18 m', 'csrf_token': Request.csrf_token(self)},
                            files={'files': ('sketch.txt', b'sketch')})
        self.assertEqual(res.status_code, 200)
        rfi.invalidate_recordset()
        self.assertEqual(rfi.state, 'answered')
        self.assertEqual(rfi.answer, '18 m')
        self.assertEqual(len(rfi.answer_attachment_ids), 1)

