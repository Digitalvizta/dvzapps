from odoo import _, fields, models
from odoo.exceptions import UserError


class RentalContract(models.Model):
    _inherit = 'dvz.rental.contract'

    def _check_before_dispatch(self):
        res = super()._check_before_dispatch()
        today = fields.Date.context_today(self)
        for contract in self:
            expired = contract.line_ids.equipment_id.document_ids.filtered(
                lambda d: d.blocks_dispatch and d.expiry_date and d.expiry_date < today)
            if expired:
                raise UserError(_(
                    'These documents are expired. Renew them before dispatching the equipment:\n%s',
                    '\n'.join(expired.mapped('display_label'))))
        return res
