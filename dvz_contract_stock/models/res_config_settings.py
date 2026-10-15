from odoo import fields, models


class ResConfigSettings(models.TransientModel):
    _inherit = 'res.config.settings'

    group_dvz_site_stores = fields.Boolean(
        'Site stores', implied_group='dvz_contract_stock.group_dvz_site_stores',
        help='Each contract gets its own store location for the material on its site.')
    group_dvz_site_transfer = fields.Boolean(
        'Transfers between sites and returns', implied_group='dvz_contract_stock.group_dvz_site_transfer')
    group_dvz_material_usage = fields.Boolean(
        'Material used on site', implied_group='dvz_contract_stock.group_dvz_material_usage')

    dvz_site_deliver = fields.Boolean(related='company_id.dvz_site_deliver', readonly=False)
    dvz_mr_check_stock = fields.Boolean(related='company_id.dvz_mr_check_stock', readonly=False)
    dvz_charge_store_issue = fields.Boolean(related='company_id.dvz_charge_store_issue', readonly=False)
    dvz_returns_reduce_budget = fields.Boolean(related='company_id.dvz_returns_reduce_budget', readonly=False)

    def set_values(self):
        super().set_values()
        # Transfers and usage need site stores: switch them off together.
        if not self.group_dvz_site_stores and (self.group_dvz_site_transfer or self.group_dvz_material_usage):
            self.group_dvz_site_transfer = False
            self.group_dvz_material_usage = False
            super().set_values()
