from odoo import _, fields, models


class DvzContract(models.Model):
    _inherit = 'dvz.contract'

    diary_ids = fields.One2many('dvz.site.diary', 'contract_id', 'Site Diaries')
    diary_count = fields.Integer(compute='_compute_diary_stats')
    diary_hours_lost_client = fields.Float('Hours lost (client / neutral)', compute='_compute_diary_stats')

    def _compute_diary_stats(self):
        Delay = self.env['dvz.site.diary.delay']
        for rec in self:
            rec.diary_count = len(rec.diary_ids)
            delays = Delay.search([('contract_id', '=', rec.id), ('diary_id.state', '=', 'approved'),
                                   ('responsible', 'in', ('client', 'neutral'))]) if rec.id else Delay
            rec.diary_hours_lost_client = sum(delays.mapped('hours_lost'))

    def action_view_diaries(self):
        self.ensure_one()
        return {
            'type': 'ir.actions.act_window',
            'name': _('Site Diaries'),
            'res_model': 'dvz.site.diary',
            'view_mode': 'list,calendar,form',
            'domain': [('contract_id', '=', self.id)],
            'context': {'default_contract_id': self.id},
        }

    def action_view_delays(self):
        self.ensure_one()
        return {
            'type': 'ir.actions.act_window',
            'name': _('Delays: %s', self.name),
            'res_model': 'dvz.site.diary.delay',
            'view_mode': 'pivot,list',
            'domain': [('contract_id', '=', self.id), ('diary_id.state', '=', 'approved')],
        }
