from odoo import _, api, fields, models


class DvzContractLine(models.Model):
    _inherit = 'dvz.contract.line'

    purchase_line_ids = fields.One2many('purchase.order.line', 'dvz_contract_line_id', 'Purchase Lines')
    request_line_ids = fields.One2many('dvz.material.request.line', 'contract_line_id', 'Material Requests')
    cost_requested = fields.Monetary('Requested', compute='_compute_procurement', store=True,
                                     help='Estimated cost of open material requests not yet on a purchase order.')
    cost_committed = fields.Monetary('Ordered', compute='_compute_procurement', store=True,
                                     help='Untaxed amount of confirmed purchase orders on this BOQ item.')
    cost_received = fields.Monetary('Received', compute='_compute_procurement', store=True)
    cost_billed = fields.Monetary('Billed', compute='_compute_procurement', store=True)
    budget_remaining = fields.Monetary('Budget Left', compute='_compute_procurement', store=True)
    budget_used_percent = fields.Float('Budget Used %', compute='_compute_procurement', store=True,
                                       aggregator='avg')
    over_budget = fields.Boolean('Over Budget', compute='_compute_procurement', store=True)

    @api.depends('cost_subtotal', 'display_type',
                 'purchase_line_ids.price_subtotal', 'purchase_line_ids.product_qty',
                 'purchase_line_ids.qty_received', 'purchase_line_ids.qty_invoiced',
                 'purchase_line_ids.order_id.state',
                 'request_line_ids.subtotal', 'request_line_ids.purchase_line_id', 'request_line_ids.request_id.state')
    def _compute_procurement(self):
        for line in self:
            requested = committed = received = billed = 0.0
            if not line.display_type:
                for req in line.request_line_ids:
                    if not req.purchase_line_id and req.request_id.state in ('draft', 'submitted', 'approved'):
                        requested += req.subtotal
                for pol in line.purchase_line_ids:
                    if pol.order_id.state != 'purchase' or pol.display_type:
                        continue
                    amount = pol._dvz_amount_in_contract_currency(pol.price_subtotal)
                    unit = amount / pol.product_qty if pol.product_qty else 0.0
                    committed += amount
                    received += unit * pol.qty_received
                    billed += unit * pol.qty_invoiced
            line.cost_requested = requested
            line.cost_committed = committed
            line.cost_received = received
            line.cost_billed = billed
            line.budget_remaining = line.cost_subtotal - committed
            line.budget_used_percent = committed / line.cost_subtotal * 100.0 if line.cost_subtotal else 0.0
            line.over_budget = bool(line.cost_subtotal and line.currency_id
                                    and line.currency_id.compare_amounts(committed, line.cost_subtotal) > 0)


class DvzContract(models.Model):
    _inherit = 'dvz.contract'

    material_request_ids = fields.One2many('dvz.material.request', 'contract_id', 'Material Requests')
    budget_line_ids = fields.One2many('dvz.contract.line', 'contract_id', 'Budget Lines',
                                      domain=[('display_type', '=', False)], readonly=True)
    material_request_count = fields.Integer(compute='_compute_procurement_counts')
    purchase_order_count = fields.Integer(compute='_compute_procurement_counts')
    over_budget_count = fields.Integer('Items Over Budget', compute='_compute_procurement_counts')
    procurement_ordered = fields.Monetary('Ordered (BOQ)', compute='_compute_procurement_counts')
    procurement_billed = fields.Monetary('Billed (BOQ)', compute='_compute_procurement_counts')

    def _compute_procurement_counts(self):
        PO = self.env['purchase.order'].sudo()
        for rec in self:
            items = rec.line_ids.filtered(lambda l: not l.display_type)
            rec.material_request_count = len(rec.material_request_ids)
            rec.purchase_order_count = PO.search_count([('dvz_contract_id', '=', rec.id)]) if rec.id else 0
            rec.over_budget_count = len(items.filtered('over_budget'))
            rec.procurement_ordered = sum(items.mapped('cost_committed'))
            rec.procurement_billed = sum(items.mapped('cost_billed'))

    def action_view_material_requests(self):
        self.ensure_one()
        return {
            'type': 'ir.actions.act_window',
            'name': _('Material Requests'),
            'res_model': 'dvz.material.request',
            'view_mode': 'list,form',
            'domain': [('contract_id', '=', self.id)],
            'context': {'default_contract_id': self.id},
        }

    def action_view_purchase_orders(self):
        self.ensure_one()
        return {
            'type': 'ir.actions.act_window',
            'name': _('Purchase Orders'),
            'res_model': 'purchase.order',
            'view_mode': 'list,form',
            'domain': [('dvz_contract_id', '=', self.id)],
            'context': {'default_dvz_contract_id': self.id},
        }

    def action_view_budget_vs_actual(self):
        self.ensure_one()
        action = self.env['ir.actions.act_window']._for_xml_id('dvz_contract_procurement.action_dvz_budget_vs_actual')
        action['domain'] = [('contract_id', '=', self.id), ('display_type', '=', False)]
        action['context'] = {}
        return action
