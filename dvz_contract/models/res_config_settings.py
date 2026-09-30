from odoo import fields, models


class ResConfigSettings(models.TransientModel):
    _inherit = "res.config.settings"

    dvz_retention_percent = fields.Float(related="company_id.dvz_retention_percent", readonly=False)
    dvz_advance_percent = fields.Float(related="company_id.dvz_advance_percent", readonly=False)
    dvz_advance_recovery_percent = fields.Float(related="company_id.dvz_advance_recovery_percent", readonly=False)
    dvz_dlp_months = fields.Integer(related="company_id.dvz_dlp_months", readonly=False)
    dvz_auto_analytic = fields.Boolean(related="company_id.dvz_auto_analytic", readonly=False)
    dvz_analytic_plan_id = fields.Many2one(related="company_id.dvz_analytic_plan_id", readonly=False)
    dvz_sale_tax_id = fields.Many2one(related="company_id.dvz_sale_tax_id", readonly=False)
    dvz_purchase_tax_id = fields.Many2one(related="company_id.dvz_purchase_tax_id", readonly=False)
    dvz_lock_boq = fields.Boolean(related="company_id.dvz_lock_boq", readonly=False)
    group_dvz_boq_cost = fields.Boolean(
        string="Estimated cost on BOQ",
        implied_group="dvz_contract.group_boq_cost",
        help="Show estimated unit cost on BOQ lines to calculate the cost budget and planned margin.")
