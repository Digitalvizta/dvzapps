from odoo import fields, models


class ResCompany(models.Model):
    _inherit = 'res.company'

    dvz_tender_overhead_percent = fields.Float('Default Overhead %', default=10.0)
    dvz_tender_profit_percent = fields.Float('Default Profit %', default=10.0)
    dvz_tender_bid_bond_percent = fields.Float('Default Bid Bond %', default=2.0)
    dvz_tender_product_id = fields.Many2one(
        'product.product', 'BOQ Item Product', domain=[('sale_ok', '=', True)],
        help='Technical product used on tender lines. Leave empty to use "BOQ Work Item".')
