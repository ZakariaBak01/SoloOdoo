"""Read-only validation for the prepared UAT-13 database."""


def require(condition, message):
    if not condition:
        raise AssertionError(message)


company_a = env["res.company"].search([("name", "=", "EL MOKRIF COMPANY SARL")], limit=1)
company_b = env["res.company"].search([("name", "=", "UAT ISOLATION COMPANY B")], limit=1)
u9 = env["res.users"].search([("login", "=", "uat.u9.documents")], limit=1)
u10 = env["res.users"].search([("login", "=", "uat.u10.document.manager")], limit=1)
u14 = env["res.users"].search([("login", "=", "uat.u14.companyb")], limit=1)
unrelated = env["res.users"].search([("login", "=", "uat.u9.unrelated")], limit=1)
chantier = env["project.project"].search([("chantier_reference", "=", "CH-UAT-001")], limit=1)

require(company_a and company_b, "UAT companies are missing.")
require(u9.has_group("elmokrif_documents_bridge.group_elmokrif_document_user"), "U9 lacks Document User.")
require(not u9.has_group("elmokrif_documents_bridge.group_elmokrif_document_manager"), "U9 must not be a Document Manager.")
require(u10.has_group("elmokrif_documents_bridge.group_elmokrif_document_manager"), "U10 lacks Document Manager.")
require(u14.company_id == company_b and company_a not in u14.company_ids, "U14 is not isolated to Company B.")
require(chantier and chantier.chantier_state == "in_progress", "CH-UAT-001 is not ready and In Progress.")
require(u9 in chantier.chantier_member_ids and u10 in chantier.chantier_member_ids, "U9/U10 are not assigned to CH-UAT-001.")
require(unrelated not in chantier.chantier_member_ids, "The same-company isolation user must remain unassigned.")

documents = env["elmokrif.document"].search([("name", "in", [
    "UAT Near Expiry Control", "UAT Past Expiry Control",
])])
require(len(documents) == 2 and all(document.state == "approved" for document in documents), "Expiry fixtures are not approved.")
require(all(not document.expiry_activity_id for document in documents), "Expiry fixtures must start without reminder activities.")
require(env["ir.attachment"].search_count([
    ("name", "in", ["uat-contract-v1.pdf", "uat-contract-v2.pdf"]),
    ("res_model", "=", False),
]) == 2, "The two contract upload fixtures are missing.")

visible_to_u9 = env["elmokrif.document"].with_user(u9).search_count([("id", "in", documents.ids)])
visible_to_manager = env["elmokrif.document"].with_user(u10).search_count([("id", "in", documents.ids)])
visible_to_unrelated = env["elmokrif.document"].with_user(unrelated).search_count([("id", "in", documents.ids)])
visible_to_u14 = env["elmokrif.document"].with_user(u14).search_count([("id", "in", documents.ids)])
require(visible_to_u9 == 2 and visible_to_manager == 2, "Assigned U9/U10 cannot see the fixtures.")
require(visible_to_unrelated == 0, "An unrelated Company A document user can see chantier documents.")
require(visible_to_u14 == 0, "U14 can see Company A documents.")

print("UAT13_DATABASE|PASS")
print(f"CHANTIER|{chantier.chantier_reference}|{chantier.chantier_state}")
print("USERS|uat.u9.documents|uat.u10.document.manager|uat.u9.unrelated|uat.u14.companyb")
print("FIXTURES|2 upload PDFs|2 approved expiry controls")
