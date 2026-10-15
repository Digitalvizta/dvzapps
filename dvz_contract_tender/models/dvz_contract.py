from odoo import fields, models


class DvzContract(models.Model):
    _inherit = 'dvz.contract'

    dvz_sale_order_id = fields.Many2one('sale.order', 'Tender', copy=False, readonly=True, index='btree_not_null')

    def action_dvz_view_tender(self):
        self.ensure_one()
        return {
            'type': 'ir.actions.act_window',
            'res_model': 'sale.order',
            'res_id': self.dvz_sale_order_id.id,
            'view_mode': 'form',
            'views': [(self.env.ref('dvz_contract_tender.dvz_tender_view_form').id, 'form')],
        }


class DvzBankGuarantee(models.Model):
    _inherit = 'dvz.bank.guarantee'

    dvz_sale_order_id = fields.Many2one('sale.order', 'Tender', index='btree_not_null',
                                        domain=[('dvz_is_tender', '=', True)])
