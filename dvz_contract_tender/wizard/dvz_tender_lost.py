from markupsafe import Markup

from odoo import _, fields, models


class DvzTenderLost(models.TransientModel):
    _name = 'dvz.tender.lost'
    _description = 'Tender Lost'

    order_id = fields.Many2one('sale.order', required=True)
    lost_reason_id = fields.Many2one('crm.lost.reason', 'Reason', required=True)
    note = fields.Text('Details', help='e.g. Competitor price 6% lower, client chose a local contractor')

    def action_confirm(self):
        self.ensure_one()
        order = self.order_id
        order._dvz_check_open_tender()
        group = order._dvz_revision_group().filtered(lambda o: o.state in ('draft', 'sent'))
        (order | group).write({'dvz_lost': True, 'dvz_lost_reason_id': self.lost_reason_id.id,
                               'dvz_lost_note': self.note})
        (order | group)._action_cancel()
        body = Markup('<b>%s</b>: %s') % (_('Tender lost'), self.lost_reason_id.name)
        if self.note:
            body += Markup('<br/>') + self.note
        order.message_post(body=body)
        lead = order.opportunity_id
        if lead and lead.active:
            lead.action_set_lost(lost_reason_id=self.lost_reason_id.id)
            lead.message_post(body=body)
        return {'type': 'ir.actions.act_window_close'}
