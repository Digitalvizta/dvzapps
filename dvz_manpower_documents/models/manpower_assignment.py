from odoo import fields, models


class ManpowerAssignment(models.Model):
    _inherit = 'dvz.manpower.assignment'

    documents_expired = fields.Boolean(related='employee_id.dv_documents_expired', string='Expired Documents')
