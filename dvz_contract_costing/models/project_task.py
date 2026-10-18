from odoo import fields, models


class ProjectTask(models.Model):
    _inherit = 'project.task'

    dvz_contract_line_id = fields.Many2one(
        'dvz.contract.line', 'BOQ Item', index='btree_not_null',
        domain="[('display_type', '=', False), ('contract_id.project_id', '=', project_id)]",
        help='Timesheets on this task are charged to this BOQ item as labour cost.')
