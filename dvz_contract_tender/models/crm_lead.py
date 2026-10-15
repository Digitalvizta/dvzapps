from odoo import _, api, fields, models
from odoo.exceptions import UserError


class CrmLead(models.Model):
    _inherit = 'crm.lead'

    dvz_tender_ids = fields.One2many('sale.order', 'opportunity_id', 'Tenders',
                                     domain=[('dvz_is_tender', '=', True)])
    dvz_tender_count = fields.Integer('Tenders', compute='_compute_dvz_tender_count')

    @api.depends('order_ids.dvz_is_tender')
    def _compute_dvz_tender_count(self):
        for lead in self:
            lead.dvz_tender_count = len(lead.order_ids.filtered(lambda o: o.dvz_is_tender and not o.dvz_superseded))

    def action_dvz_new_tender(self):
        self.ensure_one()
        if not self.partner_id:
            raise UserError(_('Set the customer on the opportunity before creating a tender.'))
        context = self._prepare_opportunity_quotation_context()
        context.update({
            'default_dvz_is_tender': True,
            'default_dvz_project_title': self.name,
            'default_require_signature': True,
        })
        return {
            'type': 'ir.actions.act_window',
            'name': _('New Tender'),
            'res_model': 'sale.order',
            'view_mode': 'form',
            'views': [(self.env.ref('dvz_contract_tender.dvz_tender_view_form').id, 'form')],
            'context': context,
        }

    def action_dvz_view_tenders(self):
        self.ensure_one()
        return {
            'type': 'ir.actions.act_window',
            'name': _('Tenders'),
            'res_model': 'sale.order',
            'view_mode': 'list,form',
            'views': [(self.env.ref('dvz_contract_tender.dvz_tender_view_list').id, 'list'),
                      (self.env.ref('dvz_contract_tender.dvz_tender_view_form').id, 'form')],
            'domain': [('opportunity_id', '=', self.id), ('dvz_is_tender', '=', True)],
            'context': dict(self._prepare_opportunity_quotation_context(), default_dvz_is_tender=True,
                            default_dvz_project_title=self.name),
        }
