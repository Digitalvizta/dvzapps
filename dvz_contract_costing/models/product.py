from odoo import fields, models

from .cost_types import PRODUCT_COST_TYPES


class ProductCategory(models.Model):
    _inherit = 'product.category'

    dvz_cost_type = fields.Selection(
        PRODUCT_COST_TYPES, string='Job Cost Type',
        help='Contract costs for products in this category are reported under this cost type, '
             'unless the product itself has a cost type.')


class ProductTemplate(models.Model):
    _inherit = 'product.template'

    dvz_cost_type = fields.Selection(
        PRODUCT_COST_TYPES, string='Job Cost Type',
        help='How contract costs for this product are reported: material, labour (e.g. a labour trade), '
             'equipment (e.g. a crane per hour), subcontract or overheads. Empty: taken from the category.')


class ProductProduct(models.Model):
    _inherit = 'product.product'

    def _dvz_cost_type(self):
        """Cost type of this product: own setting, then category (and parent categories)."""
        self.ensure_one()
        if self.dvz_cost_type:
            return self.dvz_cost_type
        categ = self.categ_id
        while categ:
            if categ.dvz_cost_type:
                return categ.dvz_cost_type
            categ = categ.parent_id
        return False
