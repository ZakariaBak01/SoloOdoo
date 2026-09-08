def post_init_hook(env):
    """Create the single dashboard record for every company already in Odoo."""
    Dashboard = env["elmokrif.dashboard"]
    for company in env["res.company"].search([]):
        if not Dashboard.search_count([("company_id", "=", company.id)]):
            Dashboard.create({"company_id": company.id})
