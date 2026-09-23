from odoo import fields


reference = "UAT-PAY-002"
payment = env["account.payment"].search([("ref", "=", reference)], limit=1)
if not payment:
    source = env["account.payment"].search([("ref", "=", "UAT-PAY-001")], limit=1)
    if not source:
        raise RuntimeError("The UAT-PAY-001 source payment is missing.")
    payment = env["account.payment"].create({
        "company_id": source.company_id.id,
        "journal_id": source.journal_id.id,
        "payment_method_line_id": source.payment_method_line_id.id,
        "payment_type": "inbound",
        "partner_type": "customer",
        "partner_id": source.partner_id.id,
        "amount": 2100,
        "currency_id": source.currency_id.id,
        "date": fields.Date.from_string("2026-10-16"),
        "ref": reference,
    })
    payment.action_post()
env.cr.commit()
print("UAT11_RETEST", payment.id, payment.name, payment.state, payment.amount, payment.ref)
