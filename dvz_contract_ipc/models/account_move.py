from odoo import fields, models


class AccountMove(models.Model):
    _inherit = 'account.move'

    dvz_contract_id = fields.Many2one('dvz.contract', 'Contract', copy=False, index='btree_not_null')
    dvz_certificate_id = fields.Many2one('dvz.contract.certificate', 'Payment Certificate', copy=False, index='btree_not_null')
    dvz_move_kind = fields.Selection(
        [('certificate', 'Payment certificate'), ('advance', 'Advance payment'), ('retention', 'Retention release')],
        string='Contract document', copy=False)
