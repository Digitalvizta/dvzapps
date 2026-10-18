from odoo import fields, models

from .cost_types import PRODUCT_COST_TYPES


class AccountAccount(models.Model):
    _inherit = 'account.account'

    dvz_cost_type = fields.Selection(
        PRODUCT_COST_TYPES, string='Job Cost Type',
        help='Used for contract costs without a product, e.g. payroll entries (labour), site office rent '
             '(site overheads) or equipment hire posted directly to an account.')
