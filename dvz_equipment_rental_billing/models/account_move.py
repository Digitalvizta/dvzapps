from odoo import fields, models


class AccountMove(models.Model):
    _inherit = 'account.move'

    dv_rental_contract_id = fields.Many2one(
        'dvz.rental.contract', string='Rental Contract', readonly=True, copy=False, index='btree_not_null')
    dv_logsheet_id = fields.Many2one(
        'dvz.equipment.logsheet', string='Equipment Log Sheet', readonly=True, copy=False)
    dv_includes_mobilization = fields.Boolean(readonly=True, copy=False)
    dv_includes_demobilization = fields.Boolean(readonly=True, copy=False)
