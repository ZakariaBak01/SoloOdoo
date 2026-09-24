"""Audit a clean UAT database and exercise its deletion rules.

Run by piping this file into ``odoo shell -d <database> --no-http``. All probe
records are rolled back, including the intentionally non-deletable chantier.
"""

from datetime import date

from odoo.exceptions import UserError


expected_companies = {"EL MOKRIF COMPANY SARL", "UAT ISOLATION COMPANY B"}
companies = env["res.company"].search([])
actual_companies = set(companies.mapped("name"))
assert actual_companies == expected_companies, (
    f"Unexpected companies: {sorted(actual_companies)}"
)

expected_logins = {"uat.admin"} | {
    f"uat.u{number}.{suffix}"
    for number, suffix in [
        (1, "manager"),
        (2, "chantier"),
        (3, "buyer"),
        (4, "purchase.approver"),
        (5, "storekeeper"),
        (6, "quality"),
        (7, "sales"),
        (8, "accountant"),
        (9, "documents"),
        (10, "document.manager"),
        (11, "employee"),
        (12, "hr.manager"),
        (13, "dashboard"),
        (14, "companyb"),
    ]
}
internal_users = env["res.users"].search([("active", "=", True), ("share", "=", False)])
actual_logins = set(internal_users.mapped("login"))
assert actual_logins == expected_logins, f"Unexpected active users: {sorted(actual_logins)}"
assert env["hr.employee"].search_count([]) == 2, "Expected only the U11/U12 employees."

business_models = [
    "project.project",
    "crm.lead",
    "sale.order",
    "purchase.order",
    "stock.picking",
    "account.move",
    "chantier.material.request",
    "chantier.quality.inspection",
    "chantier.material.consumption",
    "elmokrif.document",
    "elmokrif.bank.import",
    "elmokrif.payment.reminder",
]
counts = {model: env[model].search_count([]) for model in business_models}
nonempty = {model: count for model, count in counts.items() if count}
assert not nonempty, f"Business records remain after cleanup: {nonempty}"

try:
    company_a = companies.filtered(lambda company: company.name == "EL MOKRIF COMPANY SARL")
    manager = env["res.users"].search([("login", "=", "uat.u1.manager")], limit=1)
    warehouse = env["stock.warehouse"].search(
        [("company_id", "=", company_a.id)], limit=1
    )
    assert warehouse, "Company A has no warehouse after clean installation."

    partner_probe = env["res.partner"].create({"name": "UAT deletion probe"})
    partner_probe_id = partner_probe.id
    partner_probe.unlink()
    assert not env["res.partner"].browse(partner_probe_id).exists()

    project_probe = env["project.project"].create(
        {"name": "UAT ordinary-project deletion probe", "company_id": company_a.id}
    )
    project_probe_id = project_probe.id
    project_probe.unlink()
    assert not env["project.project"].browse(project_probe_id).exists()

    customer = env["res.partner"].create(
        {"name": "UAT protected-deletion customer", "company_id": company_a.id}
    )
    site = env["res.partner"].create(
        {"name": "UAT protected-deletion site", "company_id": company_a.id}
    )
    chantier = env["project.project"].create(
        {
            "name": "UAT protected-deletion chantier",
            "is_chantier": True,
            "company_id": company_a.id,
            "warehouse_id": warehouse.id,
            "partner_id": customer.id,
            "site_partner_id": site.id,
            "user_id": manager.id,
            "date_start": date(2026, 1, 1),
            "date": date(2026, 12, 31),
            "chantier_region": "Casablanca-Settat",
            "work_type": "construction",
        }
    )
    try:
        chantier.unlink()
    except UserError as error:
        assert "cannot be deleted" in str(error), str(error)
    else:
        raise AssertionError("Chantier deletion was not blocked by the close/archive policy.")

    print("CLEAN_AUDIT|PASS|2 companies|15 internal users|2 employees|0 business records")
    print("DELETE_PROBE|PASS|partner and ordinary project deleted without residue")
    print("CHANTIER_DELETE_POLICY|PASS|deletion blocked; close and archive required")
finally:
    env.cr.rollback()
