from odoo import fields, models


class ResCompany(models.Model):
    _inherit = 'res.company'

    dvz_retention_percent = fields.Float('Default Retention %', default=10.0)
    dvz_advance_percent = fields.Float('Default Advance %', default=0.0)
    dvz_advance_recovery_percent = fields.Float('Default Advance Recovery %', default=0.0)
    dvz_defects_months = fields.Integer('Defects Liability Period (months)', default=12)
    dvz_sale_tax_ids = fields.Many2many(
        'account.tax', 'dvz_company_sale_tax_rel', 'company_id', 'tax_id',
        string='Default Taxes (client contracts)', domain=[('type_tax_use', '=', 'sale')])
    dvz_purchase_tax_ids = fields.Many2many(
        'account.tax', 'dvz_company_purchase_tax_rel', 'company_id', 'tax_id',
        string='Default Taxes (subcontracts)', domain=[('type_tax_use', '=', 'purchase')])
    dvz_lock_boq = fields.Boolean('Lock BOQ after confirmation', default=True)
    dvz_analytic_per_contract = fields.Boolean('Analytic account per contract', default=True)
    dvz_analytic_plan_id = fields.Many2one('account.analytic.plan', string='Analytic Plan for Contracts')
