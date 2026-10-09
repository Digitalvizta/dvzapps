from odoo import fields, models


class ResCompany(models.Model):
    _inherit = 'res.company'

    dvz_mr_approval = fields.Boolean('Approve material requests', default=True)
    dvz_block_over_budget = fields.Boolean(
        'Block purchase orders over BOQ budget', default=False,
        help='If set, only contracting managers can confirm a purchase order that takes a BOQ item over its cost budget. '
             'Otherwise a warning is logged on the purchase order.')
