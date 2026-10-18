from odoo import fields, models


class ResCompany(models.Model):
    _inherit = 'res.company'

    dvz_ho_overhead_percent = fields.Float(
        'Head-Office Overhead %', default=0.0,
        help='Head-office overheads added on top of the direct cost of a contract when forecasting its final '
             'cost and margin. Set 0 if you allocate actual head-office costs instead.')
    dvz_costing_method = fields.Selection([
        ('auto', 'Remaining work at budget rates'),
        ('budget', 'Remaining budget'),
        ('manual', 'Entered by the project team'),
    ], string='Cost to Complete Method', default='auto')
