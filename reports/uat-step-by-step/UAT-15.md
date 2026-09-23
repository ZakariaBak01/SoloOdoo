# UAT-15 — Management dashboard totals and access

**Users:** U13 dashboard user; U8 reconciles accounting; U14 tests Company B. **Input:** pilot as-of date after UAT-04 through UAT-12 transactions. **Prerequisite:** at least one sales order, customer invoice/payment, PO, site consumption, opportunity and delivery.

1. U13: sign in, select Company A, open **Management Dashboard**. Set **As Of Date** to the chosen UAT date and record every displayed KPI before drilldown.
2. Click **Monthly Revenue** and compare with posted customer invoices minus credit notes for that month. Click **Unpaid Over 30 Days** and compare residuals in Accounting's aged receivables; U8 provides the source report without granting U13 accounting administrator rights.
3. Click **Pipeline Opportunities**, **Pending Supplier Orders**, and **Week Deliveries**; count the resulting records and compare to each dashboard number. Check weighted pipeline value and quotation conversion against their underlying date cohort.
4. Compare **Current Stock Value**, **Material Cost**, **Awaiting Purchase Approval**, and **Today's Absences** with Inventory, approved consumption, Purchase, and Time Off source views. Record filter dates and company for every comparison.
5. Switch to Company B in the company selector and refresh. Verify Company A record names and totals disappear. U14 opens Company B dashboard and attempts Company A card URLs; record denial.
6. UAT administrator: in a disposable role copy, remove one dashboard source permission and refresh as that role. Record whether the dashboard shows **Unavailable** rather than a misleading zero.

**Pass:** every KPI reconciles to source records with matching company/date filters and inaccessible source data is shown honestly. Record any KPI without a drilldown as a usability defect.
