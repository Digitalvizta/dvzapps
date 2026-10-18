from odoo import _, api, fields, models

from .cost_types import COST_TYPES

# Fields whose change can change the classification of a line.
CLASSIFY_TRIGGERS = {'product_id', 'employee_id', 'project_id', 'move_line_id', 'general_account_id', 'task_id', 'amount'}


class AccountAnalyticLine(models.Model):
    _inherit = 'account.analytic.line'

    dvz_contract_id = fields.Many2one('dvz.contract', 'Contract', index='btree_not_null', copy=False,
                                      help='Contract whose analytic account this line is posted on.')
    dvz_contract_line_id = fields.Many2one(
        'dvz.contract.line', 'BOQ Item', index='btree_not_null',
        domain="[('contract_id', '=', dvz_contract_id), ('display_type', '=', False)]")
    dvz_cost_type = fields.Selection(COST_TYPES, string='Cost Type', index='btree_not_null')
    dvz_cost_type_manual = fields.Boolean(
        'Cost type set by hand', copy=False,
        help='Ticked when someone changed the cost type or BOQ item; automatic classification then leaves it alone.')
    dvz_allocation_id = fields.Many2one('dvz.overhead.allocation', 'Overhead Allocation', index='btree_not_null',
                                        ondelete='cascade', copy=False, readonly=True)

    # ------------------------------------------------------------------
    # classification
    # ------------------------------------------------------------------
    def _dvz_contracts_by_account(self):
        accounts = set()
        for line in self:
            accounts.update(line._get_analytic_accounts().ids)
        if not accounts:
            return {}
        contracts = self.env['dvz.contract'].sudo().search(
            [('analytic_account_id', 'in', list(accounts))], order='id')
        result = {}
        for contract in contracts:
            current = result.get(contract.analytic_account_id.id)
            # A subcontract may share the main contract's analytic account: report on the client contract.
            if not current or (current.contract_type != 'client' and contract.contract_type == 'client'):
                result[contract.analytic_account_id.id] = contract
        return result

    def _dvz_guess_cost_type(self):
        """Cost type of one line, from where the cost comes from."""
        self.ensure_one()
        if self.dvz_allocation_id:
            return 'ho_overhead'
        if 'dvz_stock_move_id' in self._fields and self.dvz_stock_move_id:
            return 'material'
        if self.project_id and self.employee_id:      # a timesheet
            return 'labour'
        move = self.move_line_id.move_id
        if move and 'dvz_certificate_id' in move._fields and move.dvz_certificate_id \
                and move.dvz_certificate_id.contract_id.contract_type == 'subcontract':
            return 'subcontract'
        product = self.product_id or self.move_line_id.product_id
        if product:
            ctype = product._dvz_cost_type()
            if ctype:
                return ctype
        account = self.general_account_id or self.move_line_id.account_id
        if account and account.dvz_cost_type:
            return account.dvz_cost_type
        if product and product.type in ('consu', 'product'):
            return 'material'
        return 'other'

    def _dvz_is_cost(self):
        """Only real job costs count: not revenue, not customer invoices, not balance-sheet movements
        such as advances or retention on customer invoices."""
        self.ensure_one()
        if self.amount >= 0:
            return False
        account = self.general_account_id or self.move_line_id.account_id
        if account and account.account_type in ('income', 'income_other', 'asset_receivable', 'liability_payable'):
            return False
        move = self.move_line_id.move_id
        if move and move.move_type in ('out_invoice', 'out_refund', 'out_receipt'):
            return False
        if move and 'dvz_wip_run_id' in move._fields and move.dvz_wip_run_id:
            return False
        if account and account.account_type in ('asset_current', 'asset_non_current', 'asset_fixed', 'asset_cash',
                                                'liability_current', 'liability_non_current', 'equity') \
                and not account.dvz_cost_type:
            # balance-sheet lines (advances, retention, deposits) are not costs, unless marked as a cost type
            return False
        return True

    def _dvz_guess_boq(self, contract):
        self.ensure_one()
        boq = self.env['dvz.contract.line']
        pol = self.move_line_id.purchase_line_id if 'purchase_line_id' in self.move_line_id._fields else False
        if pol and pol.dvz_contract_line_id:
            boq = pol.dvz_contract_line_id
        elif 'dvz_stock_move_id' in self._fields and self.dvz_stock_move_id:
            move = self.dvz_stock_move_id
            for fname in ('dvz_contract_line_id',):
                if fname in move._fields and move[fname]:
                    boq = move[fname]
        elif self.task_id and self.task_id.dvz_contract_line_id:
            boq = self.task_id.dvz_contract_line_id
        return boq if boq and boq.contract_id == contract else self.env['dvz.contract.line']

    def _dvz_classify(self, force=False):
        """Fill contract, cost type and BOQ item. Lines changed by hand are left alone unless force=True."""
        by_account = self._dvz_contracts_by_account()
        for line in self.sudo():
            contract = self.env['dvz.contract']
            for account in line._get_analytic_accounts():
                if account.id in by_account:
                    contract = by_account[account.id]
                    break
            vals = {}
            if line.dvz_contract_id != contract:
                vals['dvz_contract_id'] = contract.id
            if not contract:
                if line.dvz_cost_type or line.dvz_contract_line_id:
                    vals.update(dvz_cost_type=False, dvz_contract_line_id=False)
            elif not line._dvz_is_cost():
                if line.dvz_cost_type and (force or not line.dvz_cost_type_manual or line.amount >= 0):
                    vals['dvz_cost_type'] = False
            elif force or not line.dvz_cost_type_manual:
                ctype = line._dvz_guess_cost_type()
                boq = line._dvz_guess_boq(contract)
                if line.dvz_cost_type != ctype:
                    vals['dvz_cost_type'] = ctype
                if boq and line.dvz_contract_line_id != boq:
                    vals['dvz_contract_line_id'] = boq.id
            if vals:
                super(AccountAnalyticLine, line).write(vals)
        return True

    @api.model_create_multi
    def create(self, vals_list):
        lines = super().create(vals_list)
        manual = lines.filtered(lambda l: l.dvz_cost_type and not l.dvz_allocation_id)
        if manual:
            super(AccountAnalyticLine, manual).write({'dvz_cost_type_manual': True})
        (lines - manual)._dvz_classify()
        manual._dvz_classify()   # still fills the contract on lines created with a cost type
        return lines

    def write(self, vals):
        if not self.env.context.get('dvz_no_manual') and ('dvz_cost_type' in vals or 'dvz_contract_line_id' in vals):
            vals = dict(vals, dvz_cost_type_manual=True)
        res = super().write(vals)
        plan_fields = set(self._get_plan_fnames()) if self else set()
        if CLASSIFY_TRIGGERS & set(vals) or plan_fields & set(vals):
            self._dvz_classify()
        return res

    def action_dvz_reclassify(self):
        """Button: forget manual changes and classify again from the source documents."""
        self.sudo().write({'dvz_cost_type_manual': False})
        self._dvz_classify(force=True)
        return {
            'type': 'ir.actions.client', 'tag': 'display_notification',
            'params': {'message': _('%s cost lines classified again.', len(self)), 'type': 'success'},
        }
