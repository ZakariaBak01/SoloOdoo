# UAT-12 — Overdue reminders, collection hold, and cheques

**Users:** U8 accountant; UAT administrator runs scheduled actions. **Inputs:** three posted unpaid UAT invoices due 7, 15 and 30 days ago; one posted outbound cheque payment numbered `UAT-CHQ-001`. **Prerequisite:** UAT-10 and test email templates configured in Company A.

1. U8: open **Accounting → Customers → Invoices**. On three disposable invoices set due dates relative to today's UAT date, post them, and confirm residual > 0. In Company A's **Overdue Invoice Reminder Templates**, verify J+7/J+15/J+30 templates are configured.
2. UAT administrator: open **Settings → Technical → Automation → Scheduled Actions**, search **EL MOKRIF queue overdue reminders**, click **Run Manually** twice. Run **EL MOKRIF refresh reminder delivery status** twice. Do not send test mail to real customer addresses.
3. U8: inspect each invoice's chatter/related reminder evidence and outgoing mail. Count one reminder per invoice and level, with due date and collector. If the reminder model has no business UI/menu, ask the UAT administrator to capture read-only technical evidence and mark U8 discoverability as a defect.
4. U8: open one unpaid invoice and click **Place on Hold** in **Collection**. Enter a reason if prompted; repeat the reminder job. Confirm no new mail is queued. Click **Release Hold** and record the audit trail.
5. Register payment on another invoice while its mail is queued but before dispatch; UAT administrator runs the refresh job. Verify queued mail becomes suppressed/cancelled. For a failed reminder, U8 attempts the available **Retry** action; if no reminder screen exposes it, record this as a UI gap.
6. U8: open **Accounting → Vendors → Payments → New** (or the Payments menu in this Odoo layout). Create a posted outbound payment using cheque method; enter cheque number `UAT-CHQ-001`, click **Save → Confirm**, then **Print Cheque**. Record print timestamp and user.
7. Create a second cheque with the same number; record the duplicate rejection. On the printed first cheque enter **Cheque Void Reason** `UAT replacement` and click **Void Cheque**. Verify the cheque state and separately inspect whether the accounting payment/journal entry still requires a standard Odoo cancellation or reversal.

**Pass:** reminders are unique and suppressed when ineligible; hold and retry are auditable; cheque number uniqueness and void reason hold. A void label must not be treated as a payment reversal without accounting evidence.
