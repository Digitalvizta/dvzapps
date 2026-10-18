from odoo import fields, models



class ResConfigSettings(models.TransientModel):
    _inherit = 'res.config.settings'

    dvz_wip_method = fields.Selection(related='company_id.dvz_wip_method', readonly=False)
    dvz_wip_journal_id = fields.Many2one(related='company_id.dvz_wip_journal_id', readonly=False)
    dvz_wip_revenue_account_id = fields.Many2one(related='company_id.dvz_wip_revenue_account_id', readonly=False)
    dvz_wip_asset_account_id = fields.Many2one(related='company_id.dvz_wip_asset_account_id', readonly=False)
    dvz_wip_liability_account_id = fields.Many2one(related='company_id.dvz_wip_liability_account_id', readonly=False)
    dvz_wip_loss_account_id = fields.Many2one(related='company_id.dvz_wip_loss_account_id', readonly=False)
    dvz_wip_provision_account_id = fields.Many2one(related='company_id.dvz_wip_provision_account_id', readonly=False)
