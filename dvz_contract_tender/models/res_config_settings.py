from odoo import fields, models


class ResConfigSettings(models.TransientModel):
    _inherit = 'res.config.settings'

    dvz_tender_overhead_percent = fields.Float(related='company_id.dvz_tender_overhead_percent', readonly=False)
    dvz_tender_profit_percent = fields.Float(related='company_id.dvz_tender_profit_percent', readonly=False)
    dvz_tender_bid_bond_percent = fields.Float(related='company_id.dvz_tender_bid_bond_percent', readonly=False)
    dvz_tender_product_id = fields.Many2one(related='company_id.dvz_tender_product_id', readonly=False)
