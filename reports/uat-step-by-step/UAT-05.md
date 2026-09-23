# UAT-05 — Material request, available stock, and shortage purchase

**Users:** U2 requests, U1 approves/plans, U5 validates transfer, U3 handles RFQ. **Input:** `CH-UAT-001`, `Cement Bag` 100 bags, `Steel Bar` 50 kg; prepare central stock of 40 cement bags and 0 steel. **Prerequisite:** chantier is In Progress and U2/U3/U4 are assigned.

1. U5: open **Inventory → Products → Products** and check on-hand central stock for Cement Bag and Steel Bar. Adjust only in the disposable UAT database so available central stock is 40 bags and 0 kg. Record actual values before continuing.
2. U2: open **EL MOKRIF → All Chantiers → CH-UAT-001 → Material Requests → New** (or **EL MOKRIF → Material Requests → New**). Choose the chantier, `WH-A`, required date one week ahead, priority **Normal**, vendor `UAT Supplier A`, and justification `UAT foundation materials`.
3. Under **Lines → Add a line**, enter Cement Bag quantity `60` bags, another Cement Bag line quantity `40` bags, and Steel Bar quantity `50` kg. Save. Verify **Available**, **Reserved**, **Procurement**, and **Outstanding** columns; use the column picker if optional columns are hidden.
4. Click **Submit**. Try editing quantities; the lines should be readonly or denied. U2 attempts **Approve** and records the denial.
5. U1: open the submitted request and click **Approve**. Click **Plan / Reserve Available Stock** once. This single button creates a site transfer for available stock and a draft purchase order for the shortage; record both smart-button counts and line quantities.
6. Click **Plan / Reserve Available Stock** again. Reopen **Site Transfers** and **Purchase Order**; verify no second transfer or PO was created and that each line points to the original request line.
7. U5: click **Site Transfers** on the request, open the transfer, enter **Done** quantity `40` cement bags, click **Validate**, and handle any Odoo backorder dialog according to its displayed quantity. Return to the request and check delivered/outstanding values.
8. U3: open the request's **Purchase Order** smart button. Verify only 60 cement bags plus 50 kg steel (adjust for the actual availability recorded in step 1). Continue in UAT-06.
9. U1: open `CH-UAT-001` and click **Put on Hold**. U2: try **New** material request or **Submit** another draft for that chantier; record the commitment blocker. U1: click **Start** to resume before other UATs.

**Pass:** the one planning action splits available stock and shortage exactly once; the request and its transfer/PO preserve source links. If stock differs, record the actual arithmetic rather than using the example totals.
