from odoo import api, SUPERUSER_ID


def migrate(cr, version):
    env = api.Environment(cr, SUPERUSER_ID, {})
    lines = env["elmokrif.bank.import.line"].search([
        ("native_statement_line_id", "=", False),
    ])
    for line in lines:
        line._ensure_native_statement_line()
        if line.state == "matched" and line.matched_payment_id:
            line._reconcile_native_payment(line.matched_payment_id)
