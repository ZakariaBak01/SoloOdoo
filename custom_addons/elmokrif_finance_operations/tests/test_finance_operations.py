import base64
from datetime import timedelta
from unittest.mock import patch

from odoo import Command, fields
from odoo.addons.account.tests.common import AccountTestInvoicingCommon
from odoo.addons.mail.models.mail_mail import MailMail as BaseMailMail
from odoo.exceptions import AccessError, UserError, ValidationError
from odoo.tests import TransactionCase, tagged


@tagged("post_install", "-at_install")
class TestFinanceOperations(TransactionCase):
    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.company = cls.env.company
        cls.bank = cls.env["account.journal"].search([
            ("company_id", "=", cls.company.id), ("type", "=", "bank")
        ], limit=1) or cls.env["account.journal"].create({
            "name": "Test Bank", "code": "TBK1", "type": "bank", "company_id": cls.company.id,
        })

    def _statement(self, content):
        return self.env["elmokrif.bank.import"].create({
            "name": "Statement", "journal_id": self.bank.id, "file_name": "statement.csv",
            "file_content": base64.b64encode(content.encode()),
        })

    def test_bank_import_is_deduplicated_reviewed_and_immutable(self):
        content = "date,amount,reference,partner\n2026-09-01,125.50,TRANSFER-1,Customer\n2026-09-01,125.50,TRANSFER-1,Customer\n"
        statement = self._statement(content)
        statement.action_import_file()
        self.assertEqual(statement.state, "imported")
        self.assertEqual(len(statement.line_ids), 1)
        line = statement.line_ids
        with self.assertRaises(AccessError):
            line.write({"amount": 999})
        line.action_mark_unmatched()
        statement.action_close()
        self.assertEqual(statement.state, "closed")
        duplicate = self._statement(content)
        with self.assertRaises(UserError):
            duplicate.action_import_file()

    def test_create_cannot_forge_finance_workflow_evidence(self):
        with self.assertRaises(UserError):
            self.env["elmokrif.bank.import"].with_context(bank_import_workflow=True).create({
                "name": "Forged", "journal_id": self.bank.id, "file_name": "x.csv",
                "file_content": base64.b64encode(b"date,amount,reference"), "state": "closed",
            })
        with self.assertRaises(AccessError):
            self.env["elmokrif.payment.reminder"].create({"invoice_id": 1, "level": "7"})
        with self.assertRaises(UserError):
            self.env["account.payment"].create({"elmokrif_cheque_state": "printed"})
        with self.assertRaises(UserError):
            self.env["account.move"].create({"move_type": "out_invoice", "elmokrif_collection_hold": True})


@tagged("post_install", "-at_install")
class TestFinanceWorkflowSafety(AccountTestInvoicingCommon):
    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.company = cls.company_data["company"]
        cls.env = cls.env(context=dict(cls.env.context, allowed_company_ids=[cls.company.id]))
        cls.bank = cls.company_data["default_journal_bank"]

    def _bank_line(self, amount=125.5, reference="TRANSFER-1", date="2026-09-01"):
        statement = self.env["elmokrif.bank.import"].create({
            "name": "Statement", "company_id": self.company.id,
            "journal_id": self.bank.id, "file_name": "statement.csv",
            "file_content": base64.b64encode(
                ("date,amount,reference\n%s,%s,%s\n" % (date, amount, reference)).encode()
            ),
        })
        statement.action_import_file()
        return statement.line_ids

    def _payment(self, direction="inbound", **values):
        payment = self.env["account.payment"].create({
            "company_id": self.company.id, "journal_id": self.bank.id,
            "payment_type": direction, "partner_type": "customer" if direction == "inbound" else "supplier",
            "partner_id": self.partner_a.id, "amount": 125.5, "ref": "TRANSFER-1", **values,
        })
        payment.action_post()
        return payment

    def _reminder(self):
        invoice = self.env["account.move"].create({
            "move_type": "out_invoice", "company_id": self.company.id,
            "partner_id": self.partner_a.id,
            "invoice_date": fields.Date.today() - timedelta(days=20),
            "invoice_date_due": fields.Date.today() - timedelta(days=20),
            "invoice_line_ids": [Command.create({
                "name": "Service", "account_id": self.company_data["default_account_revenue"].id,
                "quantity": 1, "price_unit": 100, "tax_ids": [Command.clear()],
            })],
        })
        invoice.action_post()
        template = self.env["mail.template"].create({
            "name": "Reminder", "model_id": self.env["ir.model"]._get_id("account.move"),
            "subject": "Invoice reminder", "body_html": "<p>Payment is overdue.</p>",
            "email_from": "billing@example.test", "email_to": "customer@example.test",
            "auto_delete": True,
        })
        self.company.elmokrif_reminder_template_7_id = template
        return self.env["elmokrif.payment.reminder"]._queue_for_invoice(invoice, "7")

    def test_bank_match_checks_direction_currency_and_prevents_payment_reuse(self):
        line = self._bank_line()
        outbound = self._payment("outbound")
        with self.assertRaises(ValidationError):
            line.matched_payment_id = outbound
        foreign_currency = self.env.ref("base.EUR") if self.company.currency_id != self.env.ref("base.EUR") else self.env.ref("base.USD")
        foreign_currency.active = True
        foreign = self._payment(currency_id=foreign_currency.id)
        with self.assertRaises(ValidationError):
            line.matched_payment_id = foreign
        inbound = self._payment()
        line.action_suggest_payment()
        self.assertEqual(line.matched_payment_id, inbound)
        line.action_confirm_match()
        self.assertEqual(line.state, "matched")
        other_line = self._bank_line(date="2026-09-02")
        with self.assertRaises(ValidationError):
            other_line.matched_payment_id = inbound
        with self.assertRaises(UserError):
            inbound.ref = "CHANGED"
        with self.assertRaises(AccessError):
            line.import_id.unlink()

    def test_foreign_bank_currency_and_negative_outbound_match(self):
        foreign_currency = self.env.ref("base.EUR") if self.company.currency_id != self.env.ref("base.EUR") else self.env.ref("base.USD")
        foreign_currency.active = True
        self.bank.currency_id = foreign_currency
        line = self._bank_line(amount=-125.5)
        payment = self._payment("outbound", currency_id=foreign_currency.id)
        self.assertEqual(line.currency_id, foreign_currency)
        line.matched_payment_id = payment
        line.action_confirm_match()
        self.assertEqual(line.state, "matched")

    def test_bank_csv_rejects_overflow_and_bad_columns(self):
        with self.assertRaises(ValidationError):
            self.env["elmokrif.bank.import"]._parse_amount("1e9999")
        with self.assertRaises(ValidationError):
            self._bank_line(reference="unquoted,extra-column")

    def test_reminder_is_suppressed_at_delivery_before_refresh_cron(self):
        reminder = self._reminder()
        self.assertFalse(reminder.mail_id.auto_delete)
        reminder.invoice_id.write({"elmokrif_collection_hold": True, "elmokrif_collection_hold_reason": "Disputed"})
        with patch.object(BaseMailMail, "_send") as send:
            reminder.mail_id._send()
        send.assert_not_called()
        self.assertEqual(reminder.mail_id.state, "cancel")
        self.assertEqual(reminder.state, "suppressed")

    def test_sent_reminder_keeps_delivery_evidence_after_collection_hold(self):
        reminder = self._reminder()
        reminder.mail_id.state = "sent"
        reminder.invoice_id.write({"elmokrif_collection_hold": True, "elmokrif_collection_hold_reason": "Later dispute"})
        self.env["elmokrif.payment.reminder"]._cron_refresh_reminder_statuses()
        self.assertEqual(reminder.state, "sent")

    def test_cheque_report_and_voided_evidence_are_guarded(self):
        payment = self._payment("outbound", elmokrif_cheque_number="CHQ-0001")
        report = self.env["report.elmokrif_finance_operations.report_cheque"]
        with self.assertRaises(UserError):
            report._get_report_values(payment.ids)
        payment.action_mark_cheque_printed()
        self.assertEqual(report._get_report_values(payment.ids)["docs"], payment)
        with self.assertRaises(UserError):
            payment.amount = 1
        payment.elmokrif_cheque_void_reason = "Printing spoiled"
        payment.action_void_cheque()
        with self.assertRaises(UserError):
            payment.elmokrif_cheque_void_reason = "Changed reason"
        with self.assertRaises(UserError):
            report._get_report_values(payment.ids)
        with self.assertRaises(UserError):
            payment.unlink()
