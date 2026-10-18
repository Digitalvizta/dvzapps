from odoo import fields, models, tools

from ..models.cost_types import COST_TYPES


class DvzJobCostReport(models.Model):
    _name = 'dvz.job.cost.report'
    _description = 'Job Cost Analysis'
    _auto = False
    _order = 'contract_id, contract_line_id'

    contract_id = fields.Many2one('dvz.contract', 'Contract', readonly=True)
    partner_id = fields.Many2one('res.partner', 'Client', readonly=True)
    company_id = fields.Many2one('res.company', 'Company', readonly=True)
    currency_id = fields.Many2one('res.currency', readonly=True)
    contract_line_id = fields.Many2one('dvz.contract.line', 'BOQ Item', readonly=True)
    cost_type = fields.Selection(COST_TYPES, 'Cost Type', readonly=True)
    date = fields.Date('Date', readonly=True)
    source = fields.Selection([('budget', 'Budget'), ('actual', 'Actual'), ('commit', 'Committed')],
                              readonly=True)
    budget = fields.Monetary('Budget', readonly=True)
    actual = fields.Monetary('Actual', readonly=True)
    committed = fields.Monetary('Committed (open POs)', readonly=True)
    hours = fields.Float('Labour Hours', readonly=True)
    budget_hours = fields.Float('Budget Hours', readonly=True)

    def init(self):
        tools.drop_view_if_exists(self.env.cr, self._table)
        budget_parts = []
        for ctype, col in (('material', 'budget_material'), ('labour', 'budget_labour'),
                           ('equipment', 'budget_equipment'), ('subcontract', 'budget_subcontract'),
                           ('site_overhead', 'budget_overhead'), ('other', 'budget_other')):
            budget_parts.append("""
                SELECT l.contract_id, l.id AS contract_line_id, '%(t)s' AS cost_type, c.date_start AS date,
                       'budget' AS source, l.%(col)s AS budget, 0.0 AS actual, 0.0 AS committed,
                       0.0 AS hours, %(hours)s AS budget_hours
                  FROM dvz_contract_line l JOIN dvz_contract c ON c.id = l.contract_id
                 WHERE l.display_type IS NULL AND COALESCE(l.%(col)s, 0) <> 0
            """ % {'t': ctype, 'col': col, 'hours': 'l.budget_hours' if ctype == 'labour' else '0.0'})
        query = """
            CREATE OR REPLACE VIEW %(table)s AS (
              SELECT row_number() OVER () AS id, u.contract_id, c.partner_id, c.company_id, c.currency_id,
                     u.contract_line_id, u.cost_type, u.date, u.source,
                     u.budget, u.actual, u.committed, u.hours, u.budget_hours
                FROM (
                  %(budget)s
                  UNION ALL
                  SELECT c.id, NULL, 'ho_overhead', c.date_start, 'budget',
                         c.cost_budget * COALESCE(c.ho_overhead_percent, 0) / 100.0, 0.0, 0.0, 0.0, 0.0
                    FROM dvz_contract c WHERE COALESCE(c.ho_overhead_percent, 0) <> 0
                  UNION ALL
                  SELECT a.dvz_contract_id, a.dvz_contract_line_id, a.dvz_cost_type, a.date,
                         'actual', 0.0, -a.amount, 0.0,
                         CASE WHEN a.dvz_cost_type = 'labour' THEN a.unit_amount ELSE 0.0 END, 0.0
                    FROM account_analytic_line a
                   WHERE a.dvz_contract_id IS NOT NULL AND a.dvz_cost_type IS NOT NULL
                  UNION ALL
                  SELECT bl.contract_id, pol.dvz_contract_line_id,
                         COALESCE(pt.dvz_cost_type, pc.dvz_cost_type, 'material'), po.date_order::date, 'commit',
                         0.0, 0.0,
                         GREATEST(pol.product_qty - pol.qty_invoiced, 0) * pol.price_unit, 0.0, 0.0
                    FROM purchase_order_line pol
                    JOIN purchase_order po ON po.id = pol.order_id
                    JOIN dvz_contract_line bl ON bl.id = pol.dvz_contract_line_id
                    LEFT JOIN product_product pp ON pp.id = pol.product_id
                    LEFT JOIN product_template pt ON pt.id = pp.product_tmpl_id
                    LEFT JOIN product_category pc ON pc.id = pt.categ_id
                   WHERE po.state = 'purchase' AND pol.product_qty > pol.qty_invoiced
                ) u
                JOIN dvz_contract c ON c.id = u.contract_id
            )
        """ % {'table': self._table, 'budget': ' UNION ALL '.join(budget_parts)}
        self.env.cr.execute(query)
