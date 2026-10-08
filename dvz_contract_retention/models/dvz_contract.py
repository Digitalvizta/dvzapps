from datetime import timedelta

from odoo import _, api, fields, models


class DvzContract(models.Model):
    _inherit = 'dvz.contract'

    release_ids = fields.One2many('dvz.retention.release', 'contract_id', 'Retention Releases')
    guarantee_ids = fields.One2many('dvz.bank.guarantee', 'contract_id', 'Bank Guarantees')
    guarantee_count = fields.Integer(compute='_compute_guarantee_count')
    retention_released = fields.Monetary('Retention Released', compute='_compute_retention_ledger')
    retention_balance = fields.Monetary('Retention Balance', compute='_compute_retention_ledger')

    @api.depends('release_ids.state', 'release_ids.amount', 'retention_held')
    def _compute_retention_ledger(self):
        for rec in self:
            released = sum(rec.release_ids.filtered(lambda r: r.state == 'released').mapped('amount'))
            rec.retention_released = released
            rec.retention_balance = rec.retention_held - released

    def _compute_guarantee_count(self):
        for rec in self:
            rec.guarantee_count = len(rec.guarantee_ids)

    def action_handover(self):
        res = super().action_handover()
        for rec in self:
            company = rec.company_id
            if company.dvz_release_at_handover and rec.retention_balance > 0 \
                    and not rec.release_ids.filtered(lambda r: r.release_type == 'handover' and r.state != 'cancel'):
                self.env['dvz.retention.release'].create({
                    'contract_id': rec.id,
                    'release_type': 'handover',
                    'method': 'percent',
                    'percent': company.dvz_release_handover_percent,
                })
                rec.message_post(body=_('A retention release draft was prepared at handover.'))
        return res

    def action_new_release(self):
        self.ensure_one()
        return {
            'type': 'ir.actions.act_window',
            'res_model': 'dvz.retention.release',
            'view_mode': 'form',
            'context': {
                'default_contract_id': self.id,
                'default_release_type': 'dlp_end' if self.state in ('handover', 'closed') else 'other',
                'default_percent': 100.0,
            },
        }

    def action_view_releases(self):
        self.ensure_one()
        action = self.env['ir.actions.act_window']._for_xml_id('dvz_contract_retention.action_dvz_retention_release')
        action['domain'] = [('contract_id', '=', self.id)]
        action['context'] = {'default_contract_id': self.id}
        return action

    def action_view_guarantees(self):
        self.ensure_one()
        action = self.env['ir.actions.act_window']._for_xml_id('dvz_contract_retention.action_dvz_bank_guarantee')
        action['domain'] = [('contract_id', '=', self.id)]
        action['context'] = {'default_contract_id': self.id, 'default_partner_id': self.partner_id.id,
                             'default_currency_id': self.currency_id.id}
        return action

    @api.model
    def _cron_dlp_reminders(self):
        today = fields.Date.context_today(self)
        for company in self.env['res.company'].search([]):
            days = company.dvz_dlp_reminder_days or 30
            contracts = self.search([
                ('company_id', '=', company.id),
                ('state', '=', 'handover'),
                ('dlp_end_date', '!=', False),
                ('dlp_end_date', '<=', today + timedelta(days=days)),
            ])
            for rec in contracts:
                summary = _('Defects period of %s ends: release the retention balance', rec.name)
                if rec.activity_ids.filtered(lambda a: a.summary == summary):
                    continue
                if rec.retention_balance <= 0:
                    continue
                rec.activity_schedule('mail.mail_activity_data_todo', date_deadline=rec.dlp_end_date,
                                      user_id=(rec.user_id or self.env.user).id, summary=summary)
