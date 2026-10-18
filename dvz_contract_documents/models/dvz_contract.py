from odoo import _, fields, models


class DvzContract(models.Model):
    _inherit = 'dvz.contract'

    rfi_ids = fields.One2many('dvz.rfi', 'contract_id', 'RFIs')
    submittal_ids = fields.One2many('dvz.submittal', 'contract_id', 'Submittals')
    transmittal_ids = fields.One2many('dvz.transmittal', 'contract_id', 'Transmittals')
    rfi_open_count = fields.Integer('Open RFIs', compute='_compute_doc_counts')
    submittal_open_count = fields.Integer('Submittals under review', compute='_compute_doc_counts')
    doc_overdue_count = fields.Integer('Overdue documents', compute='_compute_doc_counts')

    def _compute_doc_counts(self):
        for rec in self:
            rec.rfi_open_count = len(rec.rfi_ids.filtered(lambda r: r.state == 'sent'))
            rec.submittal_open_count = len(rec.submittal_ids.filtered(lambda s: s.state == 'submitted'))
            rec.doc_overdue_count = len(rec.rfi_ids.filtered('is_overdue')) + \
                len(rec.submittal_ids.filtered('is_overdue'))

    def _dvz_doc_action(self, model, name):
        self.ensure_one()
        return {'type': 'ir.actions.act_window', 'name': name, 'res_model': model, 'view_mode': 'list,form',
                'domain': [('contract_id', '=', self.id)], 'context': {'default_contract_id': self.id}}

    def action_view_rfis(self):
        return self._dvz_doc_action('dvz.rfi', _('RFIs'))

    def action_view_submittals(self):
        return self._dvz_doc_action('dvz.submittal', _('Submittals'))

    def action_view_transmittals(self):
        return self._dvz_doc_action('dvz.transmittal', _('Transmittals'))
