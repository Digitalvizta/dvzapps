from odoo import fields, models


class ResCompany(models.Model):
    _inherit = 'res.company'

    dvz_diary_post_labour = fields.Boolean(
        'Post labour cost from site diaries', default=True,
        help='On approval, crew hours × rate are charged to the contract as labour. Turn off if the same people '
             'already enter timesheets, to avoid counting them twice.')
    dvz_diary_post_equipment = fields.Boolean('Post equipment cost from site diaries', default=True)
    dvz_diary_approval = fields.Boolean(
        'Site diaries need approval', default=True,
        help='The site engineer submits; the project / contract manager approves. Off: submitting approves directly.')
