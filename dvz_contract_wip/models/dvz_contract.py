from odoo import _, fields, models

from .res_company import WIP_METHODS


class DvzContract(models.Model):
    _inherit = 'dvz.contract'

    wip_method = fields.Selection(WIP_METHODS, 'Revenue Recognition',
                                  default=lambda self: self.env.company.dvz_wip_method or 'cost')
    wip_percent_manual = fields.Float('Progress % (entered)', help='Used when the method is "Entered per contract".')
    wip_line_ids = fields.One2many('dvz.wip.line', 'contract_id', 'WIP History', readonly=True)
    wip_last_line_id = fields.Many2one('dvz.wip.line', compute='_compute_wip_last', string='Last WIP')
    wip_earned = fields.Monetary('Revenue Earned (last WIP)', compute='_compute_wip_last')
    wip_adjustment = fields.Monetary('Over / Under Billing (last WIP)', compute='_compute_wip_last')

    def _compute_wip_last(self):
        for rec in self:
            last = rec.wip_line_ids.filtered(lambda l: l.run_id.state == 'posted') \
                .sorted(lambda l: (l.run_id.date, l.id))[-1:]
            rec.wip_last_line_id = last
            rec.wip_earned = last.earned
            rec.wip_adjustment = last.adjustment

    def action_view_wip_lines(self):
        self.ensure_one()
        return {
            'type': 'ir.actions.act_window',
            'name': _('WIP history: %s', self.name),
            'res_model': 'dvz.wip.line',
            'view_mode': 'list,graph',
            'domain': [('contract_id', '=', self.id)],
        }
