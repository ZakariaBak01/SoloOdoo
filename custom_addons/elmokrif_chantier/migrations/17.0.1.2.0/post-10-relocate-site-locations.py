"""Move legacy chantier locations out of warehouse Stock during module upgrade."""

from odoo import SUPERUSER_ID, api


def migrate(cr, version):
    """Repair reservations before relocating each legacy site location."""
    env = api.Environment(cr, SUPERUSER_ID, {})
    projects = env["project.project"].search([
        ("is_chantier", "=", True),
        ("site_location_id", "!=", False),
        ("warehouse_id", "!=", False),
    ])
    projects._relocate_legacy_site_locations()
