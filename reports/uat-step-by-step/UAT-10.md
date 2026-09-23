# UAT-10 — Finance readiness, invoice, payment, and credit

**Users:** U8 accountant; U7 provides sales order. **Input:** a separate 30,000 MAD tax-exclusive Construction Service sales order for `CH-UAT-002`; 20% down payment = 6,000 MAD before tax; 1,000 MAD tax-exclusive credit note. **Prerequisite:** UAT-04; tax and journals configured.

1. U8: open **Accounting → Configuration → Chantier Finance Readiness → EL MOKRIF COMPANY SARL**. Read **Live Technical Checks**. Click **Approve Finance Readiness** with incomplete checklist; record the blocker.
2. Review and tick **Legal Identity**, **Chart of Accounts**, **Taxes**, **Journals/Payments**, **Inventory Valuation**, **Analytic Policy**, **Reports Reconciliation**, **Lock/Access**, and **Pilot Documents** only after checking each. In **Review Notes**, enter evidence references and report totals. Click **Save → Approve Finance Readiness**; record approver/time.
3. U7: open the confirmed 30,000 MAD sales order. Click standard **Create Invoice**, choose **Down Payment (percentage)**, enter `20`, and create draft invoice. U8: open it, verify untaxed advance `6000`, tax per configured rate, correct customer, chantier, and analytic distribution.
4. U8: click **Confirm** or **Post** on the invoice (visible standard Odoo label). Click **Register Payment**, enter a partial payment of `2000` MAD using the UAT Bank journal, and confirm. Record residual and payment status; inspect aged receivables.
5. From the sales order create the final invoice for delivered/invoiceable lines; confirm the down-payment deduction appears once. U8 posts it and checks balanced journal entries and analytic allocation.
6. U8: from the posted final invoice click **Credit Note**, enter reason `UAT price correction`, make a draft credit note for 1,000 MAD tax-exclusive, and post it. Compare the net commercial amount to the 30,000 MAD order less 1,000 MAD credit, accounting for the advance as part of settlement rather than extra revenue.
7. U8: change one critical Finance Readiness setting in a disposable test copy (or have the UAT administrator make the change), then attempt posting another draft invoice. Record whether readiness becomes invalid and posting is blocked; restore the setting afterward.

**Pass:** readiness gates posting, invoice/credit totals reconcile, analytic allocation stays on invoice lines, and the 20% advance is not double counted as revenue.
