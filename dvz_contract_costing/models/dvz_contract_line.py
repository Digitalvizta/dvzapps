from collections import defaultdict

from odoo import api, fields, models

from .cost_types import COST_TYPES, SPLIT_FIELDS


class DvzContractLine(models.Model):
    _inherit = 'dvz.contract.line'

    # ---- budget split (per unit of the BOQ item) --------------------------------------
    cost_material_unit = fields.Monetary('Material / Unit')
    cost_labour_unit = fields.Monetary('Labour / Unit')
    cost_equipment_unit = fields.Monetary('Equipment / Unit')
    cost_subcontract_unit = fields.Monetary('Subcontract / Unit')
    cost_overhead_unit = fields.Monetary('Site Overheads / Unit')
    labour_hours_unit = fields.Float('Labour Hours / Unit', digits=(16, 2))

    budget_material = fields.Monetary('Material Budget', compute='_compute_budget_split', store=True)
    budget_labour = fields.Monetary('Labour Budget', compute='_compute_budget_split', store=True)
    budget_equipment = fields.Monetary('Equipment Budget', compute='_compute_budget_split', store=True)
    budget_subcontract = fields.Monetary('Subcontract Budget', compute='_compute_budget_split', store=True)
    budget_overhead = fields.Monetary('Site Overheads Budget', compute='_compute_budget_split', store=True)
    budget_other = fields.Monetary('Not Split', compute='_compute_budget_split', store=True,
                                   help='Part of the estimated cost that is not split into cost types.')
    budget_hours = fields.Float('Budget Labour Hours', compute='_compute_budget_split', store=True)

    # ---- live job costing (not stored: always up to date) --------------------------------
    jc_actual = fields.Monetary('Actual Cost', compute='_compute_job_costing')
    jc_open_commit = fields.Monetary('Committed (open POs)', compute='_compute_job_costing')
    jc_progress = fields.Float('Progress %', compute='_compute_job_costing',
                               help='Cumulative quantity on the latest approved payment certificate.')
    jc_etc = fields.Monetary('Cost to Complete', compute='_compute_job_costing')
    jc_eac = fields.Monetary('Forecast Final Cost', compute='_compute_job_costing')
    jc_variance = fields.Monetary('Variance', compute='_compute_job_costing',
                                  help='Budget minus forecast final cost. Negative = over budget.')
    jc_margin = fields.Monetary('Forecast Margin', compute='_compute_job_costing')
    jc_margin_percent = fields.Float('Forecast Margin %', compute='_compute_job_costing')
    jc_actual_hours = fields.Float('Actual Labour Hours', compute='_compute_job_costing')
    jc_status = fields.Selection([('ok', 'On budget'), ('warn', 'Watch'), ('over', 'Over budget')],
                                 compute='_compute_job_costing', string='Status')
    etc_manual = fields.Monetary('Cost to Complete (entered)',
                                 help='Used when the contract\'s cost-to-complete method is "Entered by the project team".')

    @api.depends('quantity', 'cost_subtotal', 'display_type', 'labour_hours_unit',
                 'cost_material_unit', 'cost_labour_unit', 'cost_equipment_unit',
                 'cost_subcontract_unit', 'cost_overhead_unit')
    def _compute_budget_split(self):
        for line in self:
            qty = 0.0 if line.display_type else line.quantity
            split = 0.0
            for ctype, fname in SPLIT_FIELDS.items():
                amount = qty * line[fname]
                line['budget_%s' % ('overhead' if ctype == 'site_overhead' else ctype)] = amount
                split += amount
            line.budget_other = max((line.cost_subtotal or 0.0) - split, 0.0)
            line.budget_hours = qty * line.labour_hours_unit

    # keep the estimated unit cost equal to the split, when a split is entered
    @api.onchange(*SPLIT_FIELDS.values())
    def _onchange_cost_split(self):
        total = sum(self[f] for f in SPLIT_FIELDS.values())
        if total:
            self.cost_unit = total

    def _dvz_sync_cost_unit(self, vals):
        if not set(SPLIT_FIELDS.values()) & set(vals) or 'cost_unit' in vals:
            return
        for line in self:
            total = sum(line[f] for f in SPLIT_FIELDS.values())
            if total and line.currency_id.compare_amounts(total, line.cost_unit):
                super(DvzContractLine, line.with_context(dvz_boq_unlock=True)).write({'cost_unit': total})

    @api.model_create_multi
    def create(self, vals_list):
        for vals in vals_list:
            total = sum(vals.get(f) or 0.0 for f in SPLIT_FIELDS.values())
            if total and not vals.get('cost_unit'):
                vals['cost_unit'] = total
        return super().create(vals_list)

    def write(self, vals):
        res = super().write(vals)
        self._dvz_sync_cost_unit(vals)
        return res

    # ------------------------------------------------------------------
    # job costing
    # ------------------------------------------------------------------
    def _jc_budget_by_type(self):
        self.ensure_one()
        return {
            'material': self.budget_material, 'labour': self.budget_labour, 'equipment': self.budget_equipment,
            'subcontract': self.budget_subcontract, 'site_overhead': self.budget_overhead,
            'ho_overhead': 0.0, 'other': self.budget_other,
        }

    def _jc_actuals(self):
        """{line_id: {cost_type: cost}} and {line_id: labour hours} from the analytic items."""
        cost = defaultdict(lambda: defaultdict(float))
        hours = defaultdict(float)
        lines = self.filtered('id')
        if not lines:
            return cost, hours
        groups = self.env['account.analytic.line'].sudo()._read_group(
            [('dvz_contract_line_id', 'in', lines.ids), ('dvz_cost_type', '!=', False)],
            ['dvz_contract_line_id', 'dvz_cost_type'], ['amount:sum', 'unit_amount:sum'])
        for boq, ctype, amount, unit in groups:
            cost[boq.id][ctype] += -amount
            if ctype == 'labour':
                hours[boq.id] += unit
        return cost, hours

    def _jc_progress(self):
        """{line_id: progress 0..1} from the latest approved / invoiced payment certificate."""
        progress = {}
        lines = self.filtered('id')
        if not lines:
            return progress
        groups = self.env['dvz.contract.certificate.line'].sudo()._read_group(
            [('contract_line_id', 'in', lines.ids), ('certificate_id.state', 'in', ('approved', 'invoiced'))],
            ['contract_line_id'], ['qty_cumulative:max'])
        for boq, qty in groups:
            if boq.quantity:
                progress[boq.id] = max(0.0, min(qty / boq.quantity, 1.0))
        return progress

    def _jc_values(self):
        """Full costing per BOQ item and cost type. Returns {line_id: dict}."""
        actuals, hours = self._jc_actuals()
        progress = self._jc_progress()
        result = {}
        for line in self:
            contract = line.contract_id
            method = contract.costing_method or 'auto'
            budget = line._jc_budget_by_type()
            act = actuals.get(line.id, {})
            prog = progress.get(line.id, 0.0)
            open_commit = max((line.cost_committed or 0.0) - (line.cost_billed or 0.0), 0.0) \
                if 'cost_committed' in line._fields else 0.0
            etc = {}
            if method == 'budget':
                # remaining budget of the item, split over the cost types that still have budget left
                remaining = max(sum(budget.values()) - sum(act.values()), 0.0)
                left = {t: max(budget.get(t, 0.0) - act.get(t, 0.0), 0.0) for t, _l in COST_TYPES}
                base = sum(left.values()) or sum(budget.values())
                for ctype, _label in COST_TYPES:
                    share = (left[ctype] if sum(left.values()) else budget.get(ctype, 0.0)) / base if base else 0.0
                    etc[ctype] = remaining * share
            else:   # auto (and the split for manual, scaled below)
                for ctype, _label in COST_TYPES:
                    etc[ctype] = max(budget.get(ctype, 0.0) * (1.0 - prog), 0.0)
            total_etc = sum(etc.values())
            if method == 'manual':
                wanted = line.etc_manual or 0.0
                if total_etc:
                    etc = {k: v / total_etc * wanted for k, v in etc.items()}
                else:
                    etc = dict.fromkeys(etc, 0.0)
                    etc['other'] = wanted
                total_etc = wanted
            if open_commit > total_etc:
                # money already ordered will be spent: never forecast less than that
                etc['material'] += open_commit - total_etc
                total_etc = open_commit
            actual = sum(act.values())
            eac = actual + total_etc
            result[line.id] = {
                'budget': budget, 'actual': act, 'etc': etc,
                'actual_total': actual, 'etc_total': total_etc, 'eac_total': eac,
                'open_commit': open_commit, 'progress': prog, 'hours': hours.get(line.id, 0.0),
            }
        return result

    def _compute_job_costing(self):
        values = self.filtered(lambda l: not l.display_type and l.id)._jc_values()
        for line in self:
            v = values.get(line.id)
            if not v:
                line.update({
                    'jc_actual': 0.0, 'jc_open_commit': 0.0, 'jc_progress': 0.0, 'jc_etc': 0.0, 'jc_eac': 0.0,
                    'jc_variance': 0.0, 'jc_margin': 0.0, 'jc_margin_percent': 0.0, 'jc_actual_hours': 0.0,
                    'jc_status': False,
                })
                continue
            budget = line.cost_subtotal or sum(v['budget'].values())
            variance = budget - v['eac_total']
            margin = line.price_subtotal - v['eac_total']
            status = 'ok'
            if budget and variance < 0:
                status = 'over'
            elif budget and v['actual_total'] > budget * max(v['progress'], 0.0) * 1.1 and v['actual_total'] > 0:
                status = 'warn'
            line.update({
                'jc_actual': v['actual_total'],
                'jc_open_commit': v['open_commit'],
                'jc_progress': v['progress'] * 100.0,
                'jc_etc': v['etc_total'],
                'jc_eac': v['eac_total'],
                'jc_variance': variance,
                'jc_margin': margin,
                'jc_margin_percent': margin / line.price_subtotal * 100.0 if line.price_subtotal else 0.0,
                'jc_actual_hours': v['hours'],
                'jc_status': status,
            })

    def action_view_jc_costs(self):
        self.ensure_one()
        return {
            'type': 'ir.actions.act_window',
            'name': self.item_no and '%s %s' % (self.item_no, (self.name or '')[:40]) or (self.name or '')[:50],
            'res_model': 'account.analytic.line',
            'view_mode': 'list,pivot,form',
            'domain': [('dvz_contract_line_id', '=', self.id), ('dvz_cost_type', '!=', False)],
            'context': {'search_default_group_dvz_cost_type': 1, 'create': False},
        }
