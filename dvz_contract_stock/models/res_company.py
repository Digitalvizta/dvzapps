from odoo import _, fields, models
from odoo.exceptions import UserError

FEATURE_GROUPS = {
    'site_stores': 'dvz_contract_stock.group_dvz_site_stores',
    'site_transfer': 'dvz_contract_stock.group_dvz_site_transfer',
    'material_usage': 'dvz_contract_stock.group_dvz_material_usage',
}


class ResCompany(models.Model):
    _inherit = 'res.company'

    dvz_site_deliver = fields.Boolean(
        'Deliver contract purchases to the site store', default=True,
        help='Purchase orders linked to a contract are received straight into that contract\'s site store '
             'instead of the main warehouse.')
    dvz_mr_check_stock = fields.Boolean(
        'Check stock before buying', default=False,
        help='Material requests first take what is free in the main store and only buy the shortfall.')
    dvz_charge_store_issue = fields.Boolean(
        'Charge store material to the project', default=True,
        help='Material sent from the main store to a site is charged to that project at its current cost, '
             'and material returned to the store is credited back.')
    dvz_returns_reduce_budget = fields.Boolean(
        'Supplier returns reduce the ordered cost', default=True,
        help='Goods returned to a supplier are taken off the "Ordered" amount of their BOQ item.')
    dvz_sites_location_id = fields.Many2one('stock.location', 'Sites Parent Location', readonly=True, copy=False)
    dvz_consumption_location_id = fields.Many2one('stock.location', 'Site Consumption Location', readonly=True,
                                                  copy=False)

    # ------------------------------------------------------------------
    # Feature switches (Settings > Contracting > Site Stores)
    # ------------------------------------------------------------------
    def _dvz_feature(self, key):
        """True when the optional feature is switched on in the settings."""
        group = self.env.ref(FEATURE_GROUPS[key], raise_if_not_found=False)
        if not group:
            return False
        employee = self.env.ref('base.group_user').sudo()
        return group in employee.implied_ids

    # ------------------------------------------------------------------
    # Locations
    # ------------------------------------------------------------------
    def _dvz_warehouse(self):
        self.ensure_one()
        warehouse = self.env['stock.warehouse'].sudo().search([('company_id', '=', self.id)], order='sequence, id',
                                                               limit=1)
        if not warehouse:
            raise UserError(_('Create a warehouse for %s first (Inventory > Configuration > Warehouses).', self.name))
        return warehouse

    def _dvz_main_store(self):
        """The main store: stock location of the company's first warehouse."""
        return self._dvz_warehouse().lot_stock_id

    def _dvz_sites_parent(self):
        self.ensure_one()
        location = self.dvz_sites_location_id
        if not location or not location.active:
            warehouse = self._dvz_warehouse()
            location = self.env['stock.location'].sudo().create({
                'name': _('Sites'),
                'usage': 'view',
                'location_id': warehouse.view_location_id.id,
                'company_id': self.id,
            })
            self.sudo().dvz_sites_location_id = location
        return location

    def _dvz_consumption_location(self):
        self.ensure_one()
        location = self.dvz_consumption_location_id
        if not location or not location.active:
            location = self.env['stock.location'].sudo().create({
                'name': _('Site Consumption'),
                'usage': 'production',
                'company_id': self.id,
            })
            self.sudo().dvz_consumption_location_id = location
        return location
