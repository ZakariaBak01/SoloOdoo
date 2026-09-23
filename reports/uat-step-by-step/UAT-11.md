# UAT-11 — Bank CSV import and reconciliation

**User:** U8 accountant. **Input:** UTF-8 CSV with headers `date,amount,reference,partner,account`; example row `2026-10-15,2000,UAT-PAY-001,UAT Customer A,TEST-001`. Use the exact reference, journal, direction, currency, and amount of an already posted UAT payment for the exact-match case. **Prerequisite:** UAT-10.

1. U8: open **Accounting → Bank Imports → New**. Enter **Name** `UAT Bank 01`, Company A, the same **Bank Journal** as the posted payment, upload the CSV in **File Content**, click **Save → Import CSV**. Record line count and **Imported for Review** status.
2. On separate draft imports, upload a CSV lacking `reference`, then one with date `2026/99/99`, amount `NaN`, and a duplicate row. Click **Import CSV** each time and record the validation or deduplication result. Keep the valid import for later steps.
3. Reimport the valid CSV as a new bank import. Verify it reports no new lines rather than creating duplicates.
4. Open a valid import line. Click **Suggest Exact Match**. Verify **Matched Payment** points to the single posted payment with equal amount, same sign, journal, currency and reference. Click **Confirm Match**; record **Matched** state.
5. For an ambiguous or non-exact line, verify no match is silently chosen. Use **Mark Unmatched**, or enter **Review Note** `duplicate test row` and click **Ignore**. Click **Close** on the import only once every line is reviewed.
6. Open **Accounting → Bank** and the native reconciliation view for that journal. Verify the bank transaction exists and is actually reconciled to the payment/receivable entry. Record journal entry and reconciliation reference. A custom **Matched** state alone does not satisfy this step.

**Pass:** parsing and deduplication work, ambiguous lines stay for review, and the native Odoo bank transaction is reconciled. The current custom `Confirm Match` action only stores a payment link and state; expect step 6 to expose a defect unless a separate native reconciliation process has been completed. Record this honestly rather than marking the workflow passed on the custom status alone.
