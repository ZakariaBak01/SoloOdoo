"""Populate all client-facing apps and the management dashboard."""
from datetime import date, timedelta
import base64

company = env["res.company"].browse(1)
chantier = env["project.project"].search([("name", "=", "Atlas Marina Residence")], limit=1)
customer = env["res.partner"].search([("name", "=", "Atlas Developments SARL")], limit=1)
supplier = env["res.partner"].search([("name", "=", "Maroc Matériaux")], limit=1)
service = env["product.product"].search([("name", "=", "Structural Works Package")], limit=1)
cement = env["product.product"].search([("name", "=", "Cement 50 kg")], limit=1)

def once(model, domain, values):
    record = env[model].search(domain, limit=1)
    if not record:
        record = env[model].create(values)
    return record

# CRM pipeline: enough variety to make pipeline counts and weighted value useful.
for name, revenue, probability in [
    ("Atlas Phase II Extension", 780000, 60),
    ("Palm Gardens Renovation", 425000, 35),
    ("Rabat Business Center Fit-out", 960000, 70),
    ("Mohammedia Logistics Platform", 1350000, 25),
]:
    lead = once("crm.lead", [("name", "=", name)], {
        "name": name, "partner_id": customer.id, "type": "opportunity",
        "company_id": company.id, "expected_revenue": revenue, "probability": probability,
    })
    lead.write({"expected_revenue": revenue, "probability": probability})

# Commercial funnel: two quotations and the existing confirmed chantier order.
for label, amount in [("Palm Gardens Design Proposal", 185000), ("Rabat Fit-out Proposal", 310000)]:
    once("sale.order", [("client_order_ref", "=", label)], {
        "partner_id": customer.id, "company_id": company.id, "client_order_ref": label,
        "order_line": [(0, 0, {"product_id": service.id, "name": label, "product_uom_qty": 1, "price_unit": amount})],
    }).write({"state": "sent"})

# Confirm the supplier order so the dashboard reports outstanding supply.
purchase = env["purchase.order"].search([("partner_id", "=", supplier.id), ("chantier_id", "=", chantier.id)], limit=1)
if purchase and purchase.state == "draft":
    purchase.button_confirm()

# Finance: post a current revenue invoice and an older unpaid invoice.
for reference, amount, invoice_date, due_date in [
    ("ATLAS-MARINA-MILESTONE-01", 145000, date.today(), date.today() + timedelta(days=30)),
    ("ATLAS-MARINA-MOBILISATION", 65000, date.today() - timedelta(days=55), date.today() - timedelta(days=35)),
]:
    invoice = env["account.move"].search([("ref", "=", reference)], limit=1)
    if not invoice:
        invoice = env["account.move"].create({
            "move_type": "out_invoice", "partner_id": customer.id, "company_id": company.id,
            "invoice_date": invoice_date, "invoice_date_due": due_date, "ref": reference,
            "invoice_line_ids": [(0, 0, {"product_id": service.id, "name": reference, "quantity": 1, "price_unit": amount})],
        })
        invoice.action_post()

# Dashboard record.
dashboard = once("elmokrif.dashboard", [("company_id", "=", company.id)], {
    "company_id": company.id, "as_of_date": date.today(),
})
dashboard.write({"as_of_date": date.today()})

# HR: organisation and appraisal workflow data.
manager = once("hr.employee", [("name", "=", "Sara El Mansouri")], {
    "name": "Sara El Mansouri", "job_title": "Project Director", "company_id": company.id,
})
engineer = once("hr.employee", [("name", "=", "Youssef Amrani")], {
    "name": "Youssef Amrani", "job_title": "Site Engineer", "company_id": company.id, "parent_id": manager.id,
})
once("elmokrif.hr.appraisal", [("name", "=", "2026 Mid-Year Site Engineer Review")], {
    "name": "2026 Mid-Year Site Engineer Review", "employee_id": engineer.id,
    "manager_id": manager.id, "period_start": date(2026, 1, 1), "period_end": date(2026, 6, 30),
    "due_date": date.today() + timedelta(days=10),
})

# Finance operations: a real parsed bank-import review record.
bank = env["account.journal"].search([("company_id", "=", company.id), ("type", "=", "bank")], limit=1)
if not bank:
    bank = env["account.journal"].create({"name": "Atlas Operating Bank", "code": "ATB1", "type": "bank", "company_id": company.id})
statement = env["elmokrif.bank.import"].search([("name", "=", "September Client Collections")], limit=1)
if not statement:
    csv = "date,amount,reference,partner,account\n2026-09-18,145000,ATLAS-MARINA-MILESTONE-01,Atlas Developments,MA640001\n2026-09-19,-12960,MAROC-MATERIALS-PO,Maroc Materiaux,MA640002\n"
    statement = env["elmokrif.bank.import"].create({
        "name": "September Client Collections", "company_id": company.id, "journal_id": bank.id,
        "file_name": "september-client-collections.csv", "file_content": base64.b64encode(csv.encode()),
    })
    statement.action_import_file()

env.cr.commit()
print("FULL_CLIENT_DEMO_READY", dashboard.id, len(env["crm.lead"].search([("type", "=", "opportunity")])))
