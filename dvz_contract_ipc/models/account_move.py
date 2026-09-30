from odoo import fields, models


class AccountMove(models.Model):
    _inherit = "account.move"

    dvz_contract_id = fields.Many2one("dvz.contract", string="Contract", copy=False, index="btree_not_null")
    dvz_ipc_id = fields.Many2one("dvz.contract.ipc", string="Payment certificate", copy=False,
                                 index="btree_not_null")

    def button_cancel(self):
        res = super().button_cancel()
        self._dvz_release_ipc()
        return res

    def unlink(self):
        self._dvz_release_ipc()
        return super().unlink()

    def _dvz_release_ipc(self):
        """An IPC whose invoice is cancelled or deleted goes back to 'approved' so it can be invoiced again."""
        ipcs = self.mapped("dvz_ipc_id").filtered(lambda i: i.state == "invoiced")
        if ipcs:
            ipcs.write({"state": "approved"})
