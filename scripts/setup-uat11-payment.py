"""Create the exact posted payment used by the UAT-11 CSV fixture.

Run by piping this file into ``odoo shell -d test --no-http``. The setup is
idempotent and deliberately leaves the imported bank line in Needs Review.
"""

from datetime import date


REFERENCE = "UAT-PAY-001"
AMOUNT = 2000.0

accountant = env["res.users"].search([("login", "=", "uat.u8.accountant")], limit=1)
customer = env["res.partner"].search([("name", "=", "UAT Customer A")], limit=1)
line = env["elmokrif.bank.import.line"].search([
    ("reference", "=", REFERENCE),
    ("amount", "=", AMOUNT),
], limit=1)
if not accountant or not customer or not line:
    raise RuntimeError("U8, UAT Customer A, or the imported UAT-PAY-001 line is missing.")

journal = line.journal_id
payment_method_line = journal.inbound_payment_method_line_ids[:1]
if not payment_method_line:
    raise RuntimeError(f"Bank journal {journal.display_name} has no inbound payment method.")

payments = env["account.payment"].search([
    ("company_id", "=", line.company_id.id),
    ("journal_id", "=", journal.id),
    ("payment_type", "=", "inbound"),
    ("currency_id", "=", line.currency_id.id),
    ("amount", "=", AMOUNT),
    ("ref", "=", REFERENCE),
])
if len(payments) > 1:
    raise RuntimeError(f"Multiple exact-match payments already exist: {payments.ids}")

payment = payments[:1]
if not payment:
    payment = env["account.payment"].with_user(accountant).create({
        "company_id": line.company_id.id,
        "journal_id": journal.id,
        "payment_method_line_id": payment_method_line.id,
        "payment_type": "inbound",
        "partner_type": "customer",
        "partner_id": customer.id,
        "currency_id": line.currency_id.id,
        "amount": AMOUNT,
        "date": date(2026, 10, 15),
        "ref": REFERENCE,
    })
if payment.state == "draft":
    payment.with_user(accountant).action_post()
if payment.state != "posted":
    raise RuntimeError(f"Payment {payment.id} is not posted: {payment.state}")

candidates = env["account.payment"].search([
    ("company_id", "=", line.company_id.id),
    ("journal_id", "=", journal.id),
    ("state", "=", "posted"),
    ("amount", "=", abs(line.amount)),
    ("ref", "=", line.reference),
    ("currency_id", "=", line.currency_id.id),
    ("payment_type", "=", "inbound"),
])
if candidates != payment:
    raise RuntimeError(f"Expected one exact candidate, found payment IDs {candidates.ids}")

env.cr.commit()
print(f"UAT11_PAYMENT|READY|id={payment.id}|name={payment.name}|state={payment.state}")
print(f"MATCH_INPUT|journal={journal.display_name}|currency={line.currency_id.name}|amount={payment.amount}|reference={payment.ref}")
print(f"IMPORT_LINE|id={line.id}|state={line.state}|matched_payment={line.matched_payment_id.id or 0}")
