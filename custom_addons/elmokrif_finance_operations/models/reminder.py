from datetime import timedelta

from odoo import _, api, fields, models
from odoo.exceptions import AccessError, UserError

_REMINDER_WORKFLOW_TOKEN = object()

class ElMokrifPaymentReminder(models.Model):
    _name = "elmokrif.payment.reminder"
    _description = "EL MOKRIF Payment Reminder"
    _inherit = ["mail.thread", "mail.activity.mixin"]
    _order = "invoice_id, level"
    _check_company_auto = True

    invoice_id = fields.Many2one(
        "account.move", required=True, ondelete="restrict", check_company=True, index=True
    )
    company_id = fields.Many2one(related="invoice_id.company_id", store=True, readonly=True)
    level = fields.Selection(
        [("7", "J+7"), ("15", "J+15"), ("30", "J+30")], required=True, readonly=True
    )
    state = fields.Selection([
        ("queued", "Queued"), ("sent", "Sent"), ("failed", "Failed"),
        ("suppressed", "Suppressed"),
    ], default="queued", required=True, readonly=True, tracking=True)
    mail_id = fields.Many2one("mail.mail", readonly=True, copy=False, ondelete="set null")
    collector_id = fields.Many2one(related="invoice_id.elmokrif_collector_id", readonly=True)
    due_date = fields.Date(related="invoice_id.invoice_date_due", readonly=True)

    _sql_constraints = [
        ("invoice_level_unique", "unique(invoice_id, level)", "Only one reminder is allowed per invoice and level."),
    ]

    @api.model
    def _template_for_level(self, company, level):
        return company["elmokrif_reminder_template_%s_id" % level]

    def _workflow_write(self, values):
        return self.with_context(_elmokrif_reminder_workflow_token=_REMINDER_WORKFLOW_TOKEN).write(values)

    @api.model_create_multi
    def create(self, values_list):
        if self.env.context.get("_elmokrif_reminder_workflow_token") is not _REMINDER_WORKFLOW_TOKEN:
            raise AccessError(_("Payment reminders can only be created by the reminder workflow."))
        return super().create(values_list)

    @api.model
    def _is_eligible(self, invoice, level, today=None):
        today = today or fields.Date.today()
        return bool(
            invoice.state == "posted"
            and invoice.move_type == "out_invoice"
            and invoice.payment_state not in ("paid", "reversed", "in_payment")
            and not invoice.elmokrif_collection_hold
            and invoice.amount_residual > 0
            and invoice.invoice_date_due
            and invoice.invoice_date_due <= today - timedelta(days=int(level))
        )

    @api.model
    def _queue_for_invoice(self, invoice, level):
        if not self._is_eligible(invoice, level):
            return self.browse()
        existing = self.search([("invoice_id", "=", invoice.id), ("level", "=", level)], limit=1)
        if existing:
            return existing
        template = self._template_for_level(invoice.company_id, level)
        reminder = self.with_context(
            _elmokrif_reminder_workflow_token=_REMINDER_WORKFLOW_TOKEN
        ).create({"invoice_id": invoice.id, "level": level})
        if not template:
            reminder._workflow_write({"state": "failed"})
            reminder.activity_schedule(
                activity_type_id=self.env.ref("mail.mail_activity_data_todo").id,
                user_id=invoice.elmokrif_collector_id.id or self.env.user.id,
                summary=_("Configure overdue reminder template"),
                note=_("Configure the J+%s template before sending this reminder.") % level,
            )
            return reminder
        try:
            with self.env.cr.savepoint():
                mail_id = template.send_mail(invoice.id, force_send=False, email_values={"auto_delete": False})
        except Exception as error:
            reminder._workflow_write({"state": "failed"})
            reminder.activity_schedule(
                activity_type_id=self.env.ref("mail.mail_activity_data_todo").id,
                user_id=invoice.elmokrif_collector_id.id or self.env.user.id,
                summary=_("Overdue reminder could not be queued"),
                note=str(error),
            )
            return reminder
        reminder._workflow_write({"mail_id": mail_id})
        return reminder

    @api.model
    def _cron_queue_overdue_reminders(self):
        invoices = self.env["account.move"].search([
            ("move_type", "=", "out_invoice"), ("state", "=", "posted"),
            ("payment_state", "not in", ("paid", "reversed", "in_payment")),
            ("amount_residual", ">", 0), ("invoice_date_due", "!=", False),
        ])
        for invoice in invoices:
            for level in ("7", "15", "30"):
                self._queue_for_invoice(invoice, level)
        return True

    @api.model
    def _cron_refresh_reminder_statuses(self):
        reminders = self.search([("state", "=", "queued")])
        for reminder in reminders:
            if reminder.mail_id and reminder.mail_id.state == "sent":
                reminder._workflow_write({"state": "sent"})
                continue
            if not self._is_eligible(reminder.invoice_id, reminder.level):
                if reminder.mail_id and reminder.mail_id.state in ("outgoing", "exception"):
                    reminder.mail_id.sudo().write({"state": "cancel"})
                reminder._workflow_write({"state": "suppressed"})
                continue
            if not reminder.mail_id or reminder.mail_id.state in ("exception", "cancel"):
                reminder._workflow_write({"state": "failed"})
                reminder.activity_schedule(
                    activity_type_id=self.env.ref("mail.mail_activity_data_todo").id,
                    user_id=reminder.invoice_id.elmokrif_collector_id.id or self.env.user.id,
                    summary=_("Overdue reminder delivery failed"),
                    note=reminder.mail_id.failure_reason or _("Review the outgoing email configuration."),
                )
        return True

    def action_retry(self):
        if not self.env.user.has_group("account.group_account_manager"):
            raise AccessError(_("Only an Accounting Administrator can retry a reminder."))
        for reminder in self:
            if reminder.state != "failed" or not self._is_eligible(reminder.invoice_id, reminder.level):
                raise UserError(_("Only an eligible failed reminder can be retried."))
            template = self._template_for_level(reminder.company_id, reminder.level)
            if not template:
                raise UserError(_("Configure the company reminder template first."))
            if reminder.mail_id and reminder.mail_id.state != "sent":
                reminder.mail_id.sudo().write({"state": "cancel"})
            mail_id = template.send_mail(
                reminder.invoice_id.id, force_send=False, email_values={"auto_delete": False}
            )
            reminder._workflow_write({
                "mail_id": mail_id, "state": "queued",
            })
        return True

    def write(self, values):
        protected = {"invoice_id", "level", "state", "mail_id"}
        in_workflow = self.env.context.get("_elmokrif_reminder_workflow_token") is _REMINDER_WORKFLOW_TOKEN
        if protected.intersection(values) and not in_workflow:
            raise UserError(_("Reminder state is managed by the reminder workflow."))
        return super().write(values)

    def unlink(self):
        raise AccessError(_("Payment reminders are retained as an audit trail."))
