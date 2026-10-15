from odoo import models


class PurchaseOrder(models.Model):
    _inherit = 'purchase.order'

    def _dvz_site_destination(self):
        """Site store of the linked contract, when contract purchases are delivered to site."""
        self.ensure_one()
        contract = self.dvz_contract_id
        if not contract or contract.contract_type != 'client' or self.picking_type_id.code != 'incoming':
            return self.env['stock.location']
        company = self.company_id
        if not company.dvz_site_deliver or not company._dvz_feature('site_stores'):
            return self.env['stock.location']
        if not contract.site_location_id:
            contract._dvz_ensure_site_location()
        return contract.site_location_id

    def _get_destination_location(self):
        site = self._dvz_site_destination()
        return site.id if site else super()._get_destination_location()

    def _get_final_location_record(self):
        site = self._dvz_site_destination()
        return site or super()._get_final_location_record()
