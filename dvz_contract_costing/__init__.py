from . import models
from . import report


def _dvz_costing_post_init(env):
    """Classify the costs already posted on contracts (cost type, contract, BOQ item)."""
    lines = env['account.analytic.line'].search([])
    lines._dvz_classify()
