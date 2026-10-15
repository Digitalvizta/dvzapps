from odoo import SUPERUSER_ID, api

from odoo.addons.dvz_contracting_demo import _dvz_load_extras


def migrate(cr, version):
    if not version:
        return
    env = api.Environment(cr, SUPERUSER_ID, {})
    _dvz_load_extras(env)
