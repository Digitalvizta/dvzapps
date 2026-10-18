from odoo import fields, models


class AccountAnalyticLine(models.Model):
    _inherit = 'account.analytic.line'

    dvz_diary_id = fields.Many2one('dvz.site.diary', 'Site Diary', index='btree_not_null', ondelete='cascade',
                                   copy=False, readonly=True)
    dvz_diary_kind = fields.Selection([('labour', 'Labour'), ('equipment', 'Equipment')], copy=False, readonly=True)

    def _dvz_guess_cost_type(self):
        if self.dvz_diary_kind:
            return self.dvz_diary_kind
        return super()._dvz_guess_cost_type()
