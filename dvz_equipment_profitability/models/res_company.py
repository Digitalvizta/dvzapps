from odoo import fields, models


class ResCompany(models.Model):
    _inherit = 'res.company'

    dv_eq_fuel_price = fields.Float(
        string='Diesel Price per Litre', digits='Product Price',
        help='Used to cost the fuel on log sheets when the fuel is supplied by you.')
