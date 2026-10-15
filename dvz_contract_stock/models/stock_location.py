from odoo import api, fields, models


class StockLocation(models.Model):
    _inherit = 'stock.location'

    dvz_contract_id = fields.Many2one('dvz.contract', 'Site Store of', index='btree_not_null', copy=False,
                                      help='This location is the site store of this contract.')
    dvz_site_contract_id = fields.Many2one(
        'dvz.contract', 'Contract Site', compute='_compute_dvz_site_contract_id', store=True, recursive=True,
        index='btree_not_null', help='Contract whose site store holds this location (itself or a parent).')

    @api.depends('dvz_contract_id', 'location_id.dvz_site_contract_id')
    def _compute_dvz_site_contract_id(self):
        for location in self:
            location.dvz_site_contract_id = location.dvz_contract_id or location.location_id.dvz_site_contract_id

    def _dvz_site_contract(self):
        self.ensure_one()
        return self.dvz_site_contract_id


class StockQuant(models.Model):
    _inherit = 'stock.quant'

    dvz_site_contract_id = fields.Many2one(related='location_id.dvz_site_contract_id', string='Contract Site',
                                           store=True, index='btree_not_null')
