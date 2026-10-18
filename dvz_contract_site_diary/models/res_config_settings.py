from odoo import fields, models


class ResConfigSettings(models.TransientModel):
    _inherit = 'res.config.settings'

    dvz_diary_post_labour = fields.Boolean(related='company_id.dvz_diary_post_labour', readonly=False)
    dvz_diary_post_equipment = fields.Boolean(related='company_id.dvz_diary_post_equipment', readonly=False)
    dvz_diary_approval = fields.Boolean(related='company_id.dvz_diary_approval', readonly=False)
