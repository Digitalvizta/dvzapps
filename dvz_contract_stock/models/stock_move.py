from odoo import _, models
from odoo.tools import float_is_zero


class StockMove(models.Model):
    _inherit = 'stock.move'

    def _action_done(self, cancel_backorder=False):
        moves = super()._action_done(cancel_backorder=cancel_backorder)
        moves._dvz_post_site_costs()
        return moves

    def _dvz_post_site_costs(self):
        """Move material cost between projects when material moves between site stores and the main store.

        Purchases for a contract are charged to the project by the vendor bill (standard analytic
        distribution). Internal moves are charged here, on the analytic account of the contract:
          * site A  -> site B       : credit project A, charge project B
          * store   -> site B       : charge project B         (setting "Charge store material to the project")
          * site A  -> store        : credit project A         (same setting)
        """
        AnalyticLine = self.env['account.analytic.line'].sudo()
        vals_list = []
        for move in self:
            if move.state != 'done' or move.location_id.usage != 'internal' \
                    or move.location_dest_id.usage != 'internal':
                continue
            company = move.company_id
            if not company._dvz_feature('site_stores'):
                continue
            src = move.location_id._dvz_site_contract()
            dst = move.location_dest_id._dvz_site_contract()
            if src == dst:
                continue
            if not (src and dst) and not company.dvz_charge_store_issue:
                continue
            if AnalyticLine.search_count([('dvz_stock_move_id', '=', move.id)], limit=1):
                continue
            product = move.product_id.with_company(company)
            value = company.currency_id.round(move.product_qty * product.standard_price)
            if float_is_zero(value, precision_rounding=company.currency_id.rounding):
                continue
            label = _('%(product)s: %(src)s → %(dst)s',
                      product=product.display_name,
                      src=move.location_id.display_name, dst=move.location_dest_id.display_name)
            for contract, sign in ((src, 1), (dst, -1)):
                column = contract and contract._analytic_column()
                if not column or column not in AnalyticLine._fields:
                    continue
                vals_list.append({
                    'name': label,
                    'date': move.date.date() if move.date else False,
                    'amount': sign * value,
                    'unit_amount': sign * -move.product_qty,
                    'product_id': product.id,
                    'product_uom_id': product.uom_id.id,
                    'company_id': company.id,
                    column: contract.analytic_account_id.id,
                    'ref': move.reference or move.picking_id.name or '',
                    'dvz_stock_move_id': move.id,
                })
        if vals_list:
            AnalyticLine.create(vals_list)
