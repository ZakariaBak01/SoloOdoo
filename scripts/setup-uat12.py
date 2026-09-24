from datetime import timedelta

from odoo import Command, fields


company = env["res.company"].search([("name", "=", "EL MOKRIF COMPANY SARL")], limit=1)
customer = env["res.partner"].search([
    ("name", "=", "UAT Customer A"),
    ("company_id", "in", [False, company.id]),
], limit=1)
service = env["product.product"].search([
    ("name", "=", "Construction Service"),
    ("company_id", "in", [False, company.id]),
], limit=1)
collector = env["res.users"].search([("login", "=", "uat.u8.accountant")], limit=1)
if not all((company, customer, service, collector)):
    raise RuntimeError("UAT-12 requires Company A, UAT Customer A, Construction Service, and U8.")

today = fields.Date.context_today(collector)
invoice_specs = [
    ("UAT-12-J+7", 7, 700.0),
    ("UAT-12-J+15", 15, 1500.0),
    ("UAT-12-J+30", 30, 3000.0),
]
created_invoices = env["account.move"]
for origin, days_overdue, amount in invoice_specs:
    invoice = env["account.move"].search([
        ("company_id", "=", company.id),
        ("move_type", "=", "out_invoice"),
        ("invoice_origin", "=", origin),
    ], limit=1)
    if not invoice:
        invoice = env["account.move"].with_company(company).create({
            "company_id": company.id,
            "move_type": "out_invoice",
            "partner_id": customer.id,
            "invoice_date": today,
            "invoice_date_due": today - timedelta(days=days_overdue),
            "invoice_origin": origin,
            "payment_reference": origin,
            "elmokrif_collector_id": collector.id,
            "invoice_line_ids": [Command.create({
                "product_id": service.id,
                "name": "%s disposable overdue reminder test" % origin,
                "quantity": 1,
                "price_unit": amount,
                "tax_ids": [Command.clear()],
            })],
        })
    if invoice.state == "draft":
        invoice.action_post()
    created_invoices |= invoice

model_id = env["ir.model"]._get_id("account.move")
template_fields = {}
for level in ("7", "15", "30"):
    name = "UAT-12 J+%s Overdue Reminder" % level
    template = env["mail.template"].search([
        ("name", "=", name),
        ("model_id", "=", model_id),
    ], limit=1)
    values = {
        "name": name,
        "model_id": model_id,
        "subject": "UAT overdue reminder J+%s - {{ object.name }}" % level,
        "body_html": (
            "<p>UAT reminder for invoice <strong>{{ object.name }}</strong>.</p>"
            "<p>Due date: {{ object.invoice_date_due }}; "
            "outstanding: {{ object.amount_residual }} {{ object.currency_id.name }}.</p>"
        ),
        "email_from": "uat-reminders@example.test",
        "email_to": "uat-reminder-recipient@example.test",
        "auto_delete": False,
    }
    if template:
        template.write(values)
    else:
        template = env["mail.template"].create(values)
    template_fields["elmokrif_reminder_template_%s_id" % level] = template.id
company.write(template_fields)

env.cr.commit()
for invoice in created_invoices.sorted("invoice_date_due", reverse=True):
    print(
        "UAT12_INVOICE",
        invoice.id,
        invoice.name,
        invoice.invoice_origin,
        invoice.invoice_date_due,
        invoice.amount_total,
        invoice.amount_residual,
        invoice.state,
        invoice.payment_state,
    )
print("UAT12_TEMPLATES", template_fields)
