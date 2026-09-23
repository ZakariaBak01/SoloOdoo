"""Add cross-module records to the Atlas Marina demo scenario."""
from datetime import date, timedelta
import base64

chantier = env["project.project"].search([("name", "=", "Atlas Marina Residence")], limit=1)
company = chantier.company_id
customer = chantier.partner_id
supplier = env["res.partner"].search([("name", "=", "Maroc Matériaux")], limit=1)
boq = env["construction.boq"].search([("chantier_id", "=", chantier.id)], limit=1)
service = env["product.product"].search([("name", "=", "Structural Works Package")], limit=1)

def add(label, model, values):
    try:
        record = env[model].create(values)
        env.cr.commit()
        print("CREATED", label, record.display_name)
    except Exception as exc:
        env.cr.rollback()
        print("SKIPPED", label, str(exc).split("\n")[0])

attachment = env["ir.attachment"].create({
    "name": "Atlas Marina - Approved Drawing.pdf",
    "type": "binary",
    "datas": base64.b64encode(b"EL MOKRIF - Atlas Marina approved drawing demonstration document"),
    "mimetype": "application/pdf",
    "company_id": company.id,
})
add("controlled document", "elmokrif.document", {
    "name": "Approved Structural Drawing — Podium Slab", "company_id": company.id,
    "category": "drawing", "owner_id": env.user.id, "issue_date": date.today(),
    "attachment_id": attachment.id, "chantier_id": chantier.id,
})
add("finance readiness", "chantier.finance.readiness", {
    "company_id": company.id,
})
add("work package", "construction.work.package", {
    "title": "Podium concrete structure", "chantier_id": chantier.id,
    "manager_id": env.user.id, "responsible_id": env.user.id,
    "planned_start": date.today() - timedelta(days=10), "planned_finish": date.today() + timedelta(days=35),
    "unit": "m3", "planned_quantity": 420,
})
add("RFI", "construction.rfi", {
    "title": "Slab reinforcement clarification", "chantier_id": chantier.id,
    "responsible_id": env.user.id, "question": "Confirm reinforcement spacing at the podium slab edge.",
    "priority": "high", "response_due": date.today() + timedelta(days=4),
})
add("submittal", "construction.submittal", {
    "title": "Waterproofing technical submittal", "chantier_id": chantier.id,
    "submittal_type": "material", "submitted_by_partner_id": supplier.id, "reviewer_id": env.user.id,
    "review_due": date.today() + timedelta(days=5), "revision": "R0",
    "description": "Product data and method statement for podium waterproofing.",
})
add("change event", "construction.change.event", {
    "title": "Lobby finish upgrade request", "chantier_id": chantier.id,
    "event_date": date.today(), "reason": "client", "description": "Client requested upgraded finish: assess marble specification and programme impact.",
    "owner_id": env.user.id, "responsibility": "client",
})
add("variation order", "construction.variation.order", {
    "title": "VO-001 Lobby finish upgrade", "chantier_id": chantier.id,
    "reason": "Client finish upgrade request",
})
if boq and service:
    add("tender", "construction.tender", {
        "title": "Atlas Marina concrete supply tender", "chantier_id": chantier.id, "boq_id": boq.id,
        "tender_type": "material", "package_code": "CON-01", "submission_deadline": date.today() + timedelta(days=7),
        "buyer_id": env.user.id, "tender_manager_id": env.user.id,
    })
print("CLIENT_DEMO_ENRICHED")
