# UAT-06 — RFQ, approval threshold, and changed-order reapproval

**Users:** U3 buyer; U4 purchase approver; UAT administrator reads configured threshold. **Inputs:** request/PO from UAT-05, vendor `UAT Supplier A`, rationale `Lowest compliant quote; delivery in seven days`; threshold examples 9,999/10,000/10,001 MAD if the configured threshold is 10,000 MAD.

1. UAT administrator: open **Settings → Users & Companies → Companies → EL MOKRIF COMPANY SARL → Chantier Procurement**. Read **Purchase Approval Threshold**, **Two Person**, and **Quality Required**; record values. If threshold is not 10,000 MAD, use `threshold − 1`, `threshold`, `threshold + 1` in steps below.
2. U3: open **EL MOKRIF → Material Requests → [UAT-05 request] → Purchase Order**. Check **Vendor** `UAT Supplier A`, **Chantier**, **Material Request**, product quantities, expected date, taxes, and company. In **Selection Rationale**, enter the rationale above; attach the vendor quotation in chatter or attachment control. Click **Save**.
3. Make three separate draft RFQs tied to controlled requests with tax-exclusive totals around the threshold, or use three copies in the disposable database while preserving source links. Record **Amount Untaxed in Company Currency** and **Approval Required** for each.
4. U3: click **Confirm Order** on the below-threshold RFQ; record whether it becomes a PO directly. On the equal and above-threshold RFQs, click **Confirm Order**; verify **To Approve** if the company's threshold policy requires it.
5. U3: attempt **Approve Order** on the controlled RFQ; verify two-person rule blocks self-approval. U4: open the same RFQ and click **Approve Order**. Record approver and approved amount.
6. In a fresh draft or reopened allowed PO, U3 changes vendor, product quantity, unit price, then tax one at a time; click **Save** after each. Verify prior approval evidence is cleared and a fresh **Confirm Order → Approve Order** sequence is required before purchase commitment.
7. Open the approved PO's **Receipt** smart button. Verify the PO, request, chantier, vendor and quantities remain linked for UAT-07.

**Pass:** threshold equality follows the recorded company setting, U3 cannot approve their own controlled PO, U4 can approve, and critical edits require reapproval. Standard Odoo Purchase approval must not leave a contradictory second gate.
