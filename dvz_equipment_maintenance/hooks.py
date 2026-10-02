def post_init_hook(env):
    """Existing machines start their service plan from their current hour meter,
    so they are not all shown as "service overdue" right after installation."""
    machines = env['dvz.equipment'].with_context(active_test=False).search([('last_service_meter', '=', 0)])
    for machine in machines:
        machine.last_service_meter = machine.hour_meter
