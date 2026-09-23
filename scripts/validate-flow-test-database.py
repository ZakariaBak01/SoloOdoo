"""Validate the reusable EL MOKRIF flow-test database.

Run by piping this file into ``odoo shell -d <database> --no-http``.
The script is read-only and raises immediately when setup is incomplete.
"""


def require(condition, message):
    if not condition:
        raise AssertionError(message)


required_modules = {
    "elmokrif_calendar_bridge",
    "elmokrif_chantier",
    "elmokrif_chantier_estimation",
    "elmokrif_chantier_stock",
    "elmokrif_construction_control",
    "elmokrif_crm",
    "elmokrif_dashboard",
    "elmokrif_documents_bridge",
    "elmokrif_finance_operations",
    "elmokrif_finance_readiness",
    "elmokrif_hr_extension",
    "elmokrif_purchase_quality",
    "elmokrif_sale_chantier",
    "elmokrif_stock_controls",
    "elmokrif_tender_boq",
}
installed_modules = set(env["ir.module.module"].search([
    ("name", "in", sorted(required_modules)),
    ("state", "=", "installed"),
]).mapped("name"))
require(installed_modules == required_modules, f"Missing modules: {sorted(required_modules - installed_modules)}")

company_a = env["res.company"].search([("name", "=", "EL MOKRIF COMPANY SARL")], limit=1)
company_b = env["res.company"].search([("name", "=", "UAT ISOLATION COMPANY B")], limit=1)
require(company_a and company_b, "The two UAT companies are required.")
require(len(env["res.company"].search([])) == 2, "The flow-test database must contain exactly two companies.")
require(company_a.currency_id.name == "MAD", "Company A must use MAD.")
require(company_a.chantier_purchase_approval_threshold == 10000.0, "Purchase threshold must be MAD 10,000.")
require(company_a.chantier_purchase_two_person, "Two-person purchase approval must be enabled.")
require(company_a.chantier_quality_required, "Receipt quality inspection must be enabled.")
require(company_a.chantier_consumption_control_required, "Controlled consumption must be enabled.")

expected_roles = {
    "uat.u1.manager": ["elmokrif_chantier.group_chantier_manager"],
    "uat.u2.chantier": ["elmokrif_tender_boq.group_boq_estimator"],
    "uat.u3.buyer": ["elmokrif_purchase_quality.group_chantier_purchase_buyer"],
    "uat.u4.purchase.approver": [
        "elmokrif_purchase_quality.group_chantier_purchase_approver",
        "elmokrif_tender_boq.group_boq_reviewer",
        "elmokrif_construction_control.group_progress_certifier",
    ],
    "uat.u5.storekeeper": ["stock.group_stock_user"],
    "uat.u6.quality": ["elmokrif_purchase_quality.group_chantier_quality_inspector"],
    "uat.u7.sales": ["sales_team.group_sale_salesman"],
    "uat.u8.accountant": [
        "account.group_account_manager",
        "elmokrif_construction_control.group_progress_certifier",
    ],
    "uat.u9.documents": ["elmokrif_documents_bridge.group_elmokrif_document_user"],
    "uat.u10.document.manager": ["elmokrif_documents_bridge.group_elmokrif_document_manager"],
    "uat.u11.employee": ["elmokrif_hr_extension.group_hr_employee"],
    "uat.u12.hr.manager": ["elmokrif_hr_extension.group_hr_manager"],
    "uat.u13.dashboard": ["elmokrif_dashboard.group_elmokrif_dashboard_user"],
    "uat.u14.companyb": ["elmokrif_chantier.group_chantier_user"],
}
for login, xmlids in expected_roles.items():
    user = env["res.users"].search([("login", "=", login), ("active", "=", True)], limit=1)
    require(user, f"Missing active persona: {login}")
    for xmlid in xmlids:
        require(user.has_group(xmlid), f"{login} is missing effective access {xmlid}")

u13 = env["res.users"].search([("login", "=", "uat.u13.dashboard")], limit=1)
u14 = env["res.users"].search([("login", "=", "uat.u14.companyb")], limit=1)
require(set(u13.company_ids.ids) == {company_a.id, company_b.id}, "U13 must be allowed in both companies.")
require(u14.company_id == company_b and u14.company_ids == company_b, "U14 must be isolated to Company B.")

required_partners = {
    "UAT Customer A", "UAT Customer A Site", "UAT Supplier A", "UAT Supplier B",
}
partners = set(env["res.partner"].search([
    ("name", "in", sorted(required_partners)), ("company_id", "=", company_a.id),
]).mapped("name"))
require(partners == required_partners, f"Missing Company A contacts: {sorted(required_partners - partners)}")
require(env["res.partner"].search_count([
    ("name", "=", "UAT Company B Customer"), ("company_id", "=", company_b.id),
]) == 1, "Company B customer is missing.")

required_products = {"Construction Service", "Cement Bag", "Steel Bar", "Paint Bucket"}
products = set(env["product.template"].search([
    ("name", "in", sorted(required_products)), ("company_id", "=", company_a.id),
]).mapped("name"))
require(products == required_products, f"Missing products: {sorted(required_products - products)}")
require(env.ref("uom.product_uom_cubic_meter", raise_if_not_found=False), "Cubic metre UoM is missing.")
require(env["stock.warehouse"].search_count([("name", "=", "WH-A"), ("company_id", "=", company_a.id)]) == 1, "WH-A is missing.")
require(env["stock.warehouse"].search_count([("name", "=", "WH-B"), ("company_id", "=", company_b.id)]) == 1, "WH-B is missing.")
require(env["account.analytic.account"].search_count([
    ("name", "=", "Casablanca Sales"), ("company_id", "=", company_a.id),
]) == 1, "Casablanca Sales analytic account is missing.")
require(env["account.account"].search_count([("company_id", "=", company_a.id)]) > 0, "Company A chart of accounts is missing.")
require(env["account.tax"].search_count([("company_id", "=", company_a.id)]) > 0, "Company A taxes are missing.")
for journal_type in ("sale", "purchase", "bank"):
    require(env["account.journal"].search_count([
        ("company_id", "=", company_a.id), ("type", "=", journal_type),
    ]) > 0, f"Company A {journal_type} journal is missing.")

transaction_models = (
    "project.project", "crm.lead", "sale.order", "purchase.order",
    "stock.picking", "account.move", "chantier.material.request",
    "chantier.quality.inspection", "chantier.material.consumption",
    "elmokrif.document", "construction.boq", "construction.tender",
)
unexpected = {
    model: env[model].search_count([])
    for model in transaction_models
    if env[model].search_count([])
}
require(not unexpected, f"The baseline contains workflow transactions: {unexpected}")

print("FLOW_TEST_DATABASE|PASS")
print(f"COMPANIES|{company_a.name}|{company_b.name}")
print(f"PERSONAS|{len(expected_roles)}|plus uat.admin")
print(f"MODULES|{len(required_modules)}")
print("CONTROLS|purchase threshold=10000|two-person=yes|quality=yes|consumption=yes")
print("ACCOUNTING|chart=yes|taxes=yes|sale-purchase-bank journals=yes")
print("TRANSACTIONS|0|clean workflow baseline")
