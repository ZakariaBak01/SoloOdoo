from odoo import models


class MailMail(models.Model):
    _inherit = "mail.mail"

    def _send(self, auto_commit=False, raise_exception=False, smtp_session=None, alias_domain_id=False):
        Reminder = self.env["elmokrif.payment.reminder"].sudo()
        for mail in self:
            reminders = Reminder.search([("mail_id", "=", mail.id)])
            for reminder in reminders:
                # Recheck immediately before delivery, even when the hourly status cron
                # has not run since a payment, hold or invoice cancellation.
                self.env.cr.execute(
                    "SELECT id FROM account_move WHERE id = %s FOR UPDATE",
                    [reminder.invoice_id.id],
                )
                reminder.invoice_id.invalidate_recordset()
                if mail.state != "sent" and not Reminder._is_eligible(reminder.invoice_id, reminder.level):
                    mail.sudo().write({"state": "cancel"})
                    reminder._workflow_write({"state": "suppressed"})
            if mail.state == "cancel":
                if auto_commit:
                    self.env.cr.commit()
                continue
            super(MailMail, mail)._send(
                auto_commit=auto_commit, raise_exception=raise_exception,
                smtp_session=smtp_session, alias_domain_id=alias_domain_id,
            )
        return True
