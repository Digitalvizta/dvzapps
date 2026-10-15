from odoo import fields, models


class AccountAnalyticLine(models.Model):
    _inherit = 'account.analytic.line'

    dvz_stock_move_id = fields.Many2one('stock.move', 'Site Material Move', index='btree_not_null', copy=False,
                                        readonly=True, ondelete='set null')
