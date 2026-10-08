from odoo import _, api, fields, models
from odoo.exceptions import UserError


class DvzContract(models.Model):
    _inherit = 'dvz.contract'

    contract_type = fields.Selection(selection_add=[('subcontract', 'Subcontract')],
                                     ondelete={'subcontract': 'cascade'})
    parent_contract_id = fields.Many2one(
        'dvz.contract', 'Main Contract', index='btree_not_null', check_company=True,
        domain="[('contract_type', '=', 'client'), ('state', 'in', ('draft', 'progress', 'handover'))]")
    subcontract_ids = fields.One2many('dvz.contract', 'parent_contract_id', 'Subcontracts')
    subcontract_count = fields.Integer(compute='_compute_subcontracted')
    subcontracted_value = fields.Monetary('Subcontracted Value', compute='_compute_subcontracted')

    @api.depends('subcontract_ids.amount_untaxed', 'subcontract_ids.state')
    def _compute_subcontracted(self):
        for rec in self:
            subs = rec.subcontract_ids.filtered(lambda s: s.state != 'cancel')
            rec.subcontract_count = len(rec.subcontract_ids)
            rec.subcontracted_value = sum(subs.mapped('amount_untaxed'))

    @api.model
    def default_get(self, fields_list):
        res = super().default_get(fields_list)
        if res.get('contract_type') == 'subcontract' or self.env.context.get('default_contract_type') == 'subcontract':
            company = self.env['res.company'].browse(res.get('company_id')) if res.get('company_id') else self.env.company
            if 'tax_ids' in fields_list:
                res['tax_ids'] = [(6, 0, company.dvz_purchase_tax_ids.ids)]
        return res

    @api.onchange('parent_contract_id')
    def _onchange_parent_contract_id(self):
        if self.parent_contract_id:
            self.project_id = self.parent_contract_id.project_id
            self.currency_id = self.parent_contract_id.currency_id
            if not self.date_end:
                self.date_end = self.parent_contract_id.date_end

    def _get_or_create_analytic_account(self):
        self.ensure_one()
        if self.contract_type == 'subcontract' and self.parent_contract_id and self.company_id.dvz_sub_use_main_analytic:
            if not self.parent_contract_id.analytic_account_id:
                raise UserError(_('Confirm the main contract %s first, so it has an analytic account.',
                                  self.parent_contract_id.name))
            return self.parent_contract_id.analytic_account_id
        return super()._get_or_create_analytic_account()

    def action_confirm(self):
        for rec in self:
            if rec.contract_type == 'subcontract' and rec.parent_contract_id and rec.company_id.dvz_sub_use_main_analytic \
                    and not rec.analytic_account_id:
                rec.analytic_account_id = rec._get_or_create_analytic_account()
        return super().action_confirm()

    def action_new_subcontract(self):
        self.ensure_one()
        return {
            'type': 'ir.actions.act_window',
            'name': _('New Subcontract'),
            'res_model': 'dvz.contract',
            'view_mode': 'form',
            'views': [(self.env.ref('dvz_contract_subcontract.dvz_subcontract_view_form').id, 'form')],
            'context': {
                'default_contract_type': 'subcontract',
                'default_parent_contract_id': self.id,
                'default_project_id': self.project_id.id,
                'default_currency_id': self.currency_id.id,
                'default_date_end': self.date_end,
            },
        }

    def action_view_subcontracts(self):
        self.ensure_one()
        action = self.env['ir.actions.act_window']._for_xml_id('dvz_contract_subcontract.action_dvz_subcontract')
        action['domain'] = [('parent_contract_id', '=', self.id)]
        action['context'] = {'default_contract_type': 'subcontract', 'default_parent_contract_id': self.id,
                             'default_project_id': self.project_id.id}
        return action

    def action_view_certificates(self):
        action = super().action_view_certificates()
        if self.contract_type == 'subcontract':
            action['name'] = _('Subcontractor Certificates')
        return action

    # advance payment to a subcontractor = vendor bill on the advances paid account
    def _dvz_advance_move_type(self):
        return 'in_invoice' if self.contract_type == 'subcontract' else super()._dvz_advance_move_type()

    def _dvz_advance_journal(self):
        if self.contract_type == 'subcontract':
            journal = self.company_id.dvz_sub_journal_id or self.env['account.journal'].search([
                ('company_id', '=', self.company_id.id), ('type', '=', 'purchase')], limit=1)
            return journal
        return super()._dvz_advance_journal()

    def _dvz_advance_account(self):
        if self.contract_type == 'subcontract':
            return self.company_id.dvz_sub_advance_account_id
        return super()._dvz_advance_account()
