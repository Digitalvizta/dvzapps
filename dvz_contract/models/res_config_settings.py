from odoo import fields, models


class ResConfigSettings(models.TransientModel):
    _inherit = 'res.config.settings'

    dvz_retention_percent = fields.Float(related='company_id.dvz_retention_percent', readonly=False)
    dvz_advance_percent = fields.Float(related='company_id.dvz_advance_percent', readonly=False)
    dvz_advance_recovery_percent = fields.Float(related='company_id.dvz_advance_recovery_percent', readonly=False)
    dvz_defects_months = fields.Integer(related='company_id.dvz_defects_months', readonly=False)
    dvz_sale_tax_ids = fields.Many2many(related='company_id.dvz_sale_tax_ids', readonly=False)
    dvz_purchase_tax_ids = fields.Many2many(related='company_id.dvz_purchase_tax_ids', readonly=False)
    dvz_lock_boq = fields.Boolean(related='company_id.dvz_lock_boq', readonly=False)
    dvz_analytic_per_contract = fields.Boolean(related='company_id.dvz_analytic_per_contract', readonly=False)
    dvz_analytic_plan_id = fields.Many2one(related='company_id.dvz_analytic_plan_id', readonly=False)
    group_dvz_show_cost = fields.Boolean(
        'Estimated cost on BOQ', implied_group='dvz_contract.group_dvz_show_cost',
        help='Show estimated unit cost, cost budget and planned margin on contracts.')
