from odoo import _, api, fields, models


class HrEmployee(models.Model):
    _inherit = 'hr.employee'

    dv_document_ids = fields.One2many('dvz.worker.document', 'employee_id', string='Worker Documents')
    dv_document_count = fields.Integer(compute='_compute_dv_document_stats')
    dv_documents_expired = fields.Boolean(compute='_compute_dv_document_stats', string='Has Expired Documents')

    @api.depends('dv_document_ids.status')
    def _compute_dv_document_stats(self):
        for employee in self:
            employee.dv_document_count = len(employee.dv_document_ids)
            employee.dv_documents_expired = any(d.status == 'expired' for d in employee.dv_document_ids)

    def action_dv_view_documents(self):
        self.ensure_one()
        return {
            'type': 'ir.actions.act_window',
            'name': _('Worker Documents'),
            'res_model': 'dvz.worker.document',
            'view_mode': 'list,form',
            'domain': [('employee_id', '=', self.id)],
            'context': {'default_employee_id': self.id},
        }
