# UAT-20 — Change event and approved variation

**Users:** U2 documents change, U1 approves, U4 reviews BOQ revision. **Input:** RFI from UAT-19, estimated cost impact 2,000 MAD, revenue impact 3,000 MAD, schedule impact 2 days, customer approval reference `UAT-CO-001`. **Prerequisite:** current approved BOQ from UAT-22.

1. U2: open **EL MOKRIF → Project Control → Change Events** and the event created from the RFI. Enter title `UAT slab design change`, **Reason** Design change, responsibility Customer, owner U2, impacts 2000/3000/2; click **Save → Submit** without evidence and record blocker.
2. Attach revised drawing and customer request, click **Save → Submit → Start Estimating**. Record detailed estimate; click **Commercial Review**. U1: click **Accept for Variation**.
3. U1: click **Create Variation Order**. Return to the event and attempt the same action again if offered; verify it opens the same variation and does not create a second one.
4. On the variation, add a line for the affected **BOQ Line**, **Quantity Delta** `1`, **Cost Amount** `2000`, **Revenue Amount** `3000`, and a description. Click **Save → Submit for Review → Request Customer Approval**.
5. U1: click **Approve Variation** without **Customer Approval Reference** or signed attachment; record blocker. Enter `UAT-CO-001`, attach dummy signed approval, save, then click **Approve Variation**. Compare Original vs Current Budget and Contract: approved cost +2000, approved revenue +3000; pending/draft changes must not affect current totals.
6. Click **Prepare BOQ Revision**. U2: open the new draft in **Tendering & BOQ → Bills of Quantities**, update the affected manual quantity, and inspect **Revision Changes**. The approved predecessor must stay unchanged. Click **Submit for Review**.
7. U4: click **Complete Review**. U1: click **Approve Baseline**. Return to the variation and click **Mark Implemented**. Verify change source and new BOQ revision links.

**Pass:** conversion is unique; approval requires customer evidence; only approved variation changes current totals; original BOQ stays immutable and revised quantities live on a new approved revision.
