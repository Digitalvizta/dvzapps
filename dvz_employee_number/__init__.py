# -*- coding: utf-8 -*-
from . import models

def pre_init_check(cr):
    from odoo.service import common
    from odoo import api, fields, models, SUPERUSER_ID, _
    from odoo.exceptions import AccessError, UserError, ValidationError
    version_info = common.exp_version()
    server_serie = version_info.get('server_serie')
    if server_serie != '16.0':
        raise UserError(_(
                    "Module support Odoo version 16.0"))
    return True

# vim:expandtab:smartindent:tabstop=4:softtabstop=4:shiftwidth=4:


def post_init_hook(cr, registry):
    from odoo import api, SUPERUSER_ID, tools
    import logging

    _logger = logging.getLogger(__name__)
    env = api.Environment(cr, SUPERUSER_ID, {})

    # Search for the server action by its name
    action = env['ir.actions.server'].search([('name', '=', 'Generate Employee Sequences')], limit=1)

    if action:
        # Execute the server action
        action.create_action()
    else:
        # Log or handle the case where the server action is not found
        _logger.warning("Server action 'Generate Employee Sequences' not found.")