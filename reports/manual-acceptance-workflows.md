# EL MOKRIF Manual Acceptance Workflows

## Purpose

Use this workbook in a disposable or demo company before production use. Record the tester, date, record links, screenshots, and result for every workflow. A failed expected result is a defect; do not work around it by changing data directly in the database.

## Test users and seed data

Create separate users so permissions are real:

| Code | Role | Required access |
|---|---|---|
| U1 | Chantier manager | EL MOKRIF Chantier Manager |
| U2 | Site user | EL MOKRIF Chantier User |
| U3 | Buyer | Purchase user; not the purchase approver |
| U4 | Quality officer | Quality access |
| U5 | Salesperson | Sales user |
| U6 | Accountant | Accounting manager |
| U7 | Dashboard user | EL MOKRIF Dashboard User only |
| U8 | HR employee | EL MOKRIF HR Employee |
| U9 | HR manager | EL MOKRIF HR Manager |

Create one customer, one vendor, one warehouse, a stockable concrete-related product, a service product, and a tax. Use two companies for the company-isolation checks.

## WF-01: Create and initialize a chantier

1. Sign in as U1 and open **EL MOKRIF → New Chantier**.
2. Enter customer, site address, warehouse, work type, planned dates, and chantier manager.
3. Save. Confirm the chantier is **Draft** and has no editable manual reference.
4. Click **Approve and Initialize**.
5. Confirm its reference, dedicated analytic account, and site stock location are created.
6. Click **Start**.

Expected: only a chantier manager can create/approve; the chantier progresses Draft → Approved → In Progress; duplicate initialization does not create duplicate analytic accounts or locations.

Evidence: chantier form, analytic account, site stock location.

## WF-02: CRM opportunity to chantier quotation

1. As U5, create an opportunity with customer, expected revenue, site, and required business information.
2. Attempt to qualify it with mandatory information missing.
3. Complete the information and qualify it.
4. Create a quotation, select the initialized chantier, add a product line, send it, then confirm it.
5. Create the customer invoice from the sales order.

Expected: incomplete qualification is refused; confirmed sales order and invoice retain the chantier and analytic allocation; changing the chantier after confirmation is refused.

Evidence: opportunity, sales order, invoice line analytic distribution.

## WF-03: Materials request, purchasing, receiving, and quality

1. As U2, create a **Material Request** for the in-progress chantier and add the stockable product.
2. Attempt submission with no lines and with a negative quantity.
3. Submit the valid request.
4. As U1, approve it and create the warehouse transfer or purchase flow.
5. As U3, create the linked purchase order, set vendor and price, then request approval where the configured threshold requires it.
6. As U1, approve; receive goods; complete quality inspection if enabled.
7. Deliver material to the chantier site location.

Expected: only draft requests are editable; self-approval restrictions apply; request, purchase, receipt, inspection, and transfer retain the chantier link; rejected quality stock cannot be consumed.

Evidence: request, purchase order approval evidence, picking, quality inspection.

## WF-04: Site consumption and material valuation

1. As U2, create a chantier material consumption using material present at the site location.
2. Try consumption before the chantier is In Progress and try more than available stock.
3. Submit and approve consumption under the configured two-person rule.
4. Validate the stock operation.
5. Open the chantier **Materials** tab.

Expected: invalid state and excess quantity are refused; approved consumption posts from the site location; the historical material valuation and material summary update.

Evidence: consumption approval record, completed picking, chantier material cost.

## WF-05: Controlled documents

1. Create a controlled document, attach a file, submit it for review, then approve it.
2. Attempt to replace the approved file, mark it public, or change its revision directly.
3. Create a revision through the documented revision flow.
4. As a user outside the authorized document scope, try opening the attachment.

Expected: approved evidence remains immutable; revision creates independent controlled evidence; unauthorized attachment access is denied.

Evidence: document chatter, attachment access-denied screen, revision record.

## WF-06: Calendar and site visit

1. As U5, create a calendar event linked to the opportunity and chantier.
2. Try selecting a chantier from the other company.
3. Open the opportunity and confirm the visit reference is available.

Expected: calendar and opportunity links remain consistent; cross-company links are rejected.

## WF-07: Finance readiness, invoicing, collection, and cheque controls

1. As U6, open Finance Readiness and complete all mandatory checks, then approve it.
2. Attempt to post a chantier invoice before approval; then post it after approval.
3. Add a collection hold with a reason and confirm reminders are suppressed while held.
4. Create a cheque payment; attempt duplicate cheque number in the same company.
5. Import a bank file with a duplicate transaction and with malformed columns.

Expected: chantier financial documents cannot post without approved readiness; collection holds preserve evidence; cheque duplication and malformed/duplicate bank imports are rejected.

Evidence: readiness record, posted invoice, hold reason, payment, bank-import results.

## WF-08: Management dashboard and company isolation

1. As U7, open the management dashboard.
2. Confirm current chantier, pipeline, material, finance, and absence KPIs appear without opening underlying restricted HR records.
3. Switch to the other company and confirm its dashboard is separate.
4. Attempt to open a restricted purchase, finance, or HR record from the dashboard user.

Expected: dashboard shows authorized aggregates only; no cross-company data leaks; dashboard-only user cannot browse protected operational records.

## WF-09: HR leave, appraisal, contract expiry, and recruitment

1. As U8, submit a leave request for self; attempt one for another employee.
2. As U9, record a refusal reason and refuse one request; use two-step approval and HR cancellation on another.
3. Create an appraisal as HR officer; complete employee self-assessment and manager review; complete it; attempt direct state/evidence editing; reopen it with a reason.
4. Create a dated contract within the expiry lead period and run the expiry activity process twice.
5. Create a recruitment applicant and convert the applicant to an employee.
6. As a standard HR user outside the custom HR Officer group, attempt direct download of a confidential employee attachment.

Expected: self-service scope is enforced; refusal/cancellation evidence is protected; appraisals follow their state flow; expiry activity is idempotent; applicant conversion creates an employee; confidential attachment download is denied.

## WF-10: Construction estimate, quantities, logistics, and tax

1. Install **EL MOKRIF Chantier Estimation** and create an estimate from an existing chantier.
2. Enter a structure type, dimensions, material mix assumptions, costs, labour productivity, machinery, truck capacity, wastage, expansion/compaction, contingency, tax, and phase percentages totaling 100.
3. Confirm net volume, procurement volume, cement bags, sand, gravel, water, truck trips, labour hours, cost subtotal, tax, and total cost.
4. Try dimensions of zero, negative allowances, phase totals other than 100, and zero truck capacity.

Expected: calculations update immediately; invalid inputs are refused; configured company tax is used.

## WF-11: Estimate revision and variance approval

1. Create an estimate in Draft, submit it, and approve it as U1.
2. Try editing every budget driver on the approved estimate: dimensions, material rates, labour rate, machinery rate, tax, contingency, and phase percentages.
3. Create a revision, change values there, submit/approve it, and confirm the earlier approved estimate becomes Superseded.
4. Force an overrun through actual cost and approve the variance as U1.

Expected: only the approved workflow creates an approved baseline; approved estimates cannot be overwritten; a single latest approved revision is the active baseline; variance approval is manager-only.

## WF-12: Daily site reports, live progress, and forecast

1. Create chantier tasks with a mix of open and folded/completed stages.
2. Add daily reports with quantities, labour hours, equipment hours/costs, weather, oblockers, notes, photos, and cost codes.
3. Open the estimate **Live Cost Control** tab.
4. Add actual stock consumption, then refresh the estimate.
5. Confirm actual material cost, labour/equipment/other costs, actual total, progress, expected cost at progress, budget consumed, variance, and forecast final cost.

Expected: task completion drives progress when tasks exist; manual progress is used only when no tasks exist; actual financial values update from their source records; an overrun warning appears when spending is ahead of progress.

## WF-13: Cost-code traceability and cash flow

1. Use the standard cost codes on material movements, purchase lines, sales lines, and invoice lines.
2. Create a purchase commitment, a supplier bill, customer invoice, customer payment, and a customer refund for the same chantier.
3. Review chantier budget, commitment, actual cost, invoiced revenue, collected cash, margin, and phase cash forecast by cost code.

Expected: every financial and material transaction is attributable to chantier and cost code; refunds reduce revenue; payments affect collected cash; commitments remain visible before supplier billing.

## WF-14: Security regression and closeout

1. Use U2, U7, U8, and a user from the second company to attempt direct URL access to records outside their scope.
2. Attempt to alter approved workflow evidence through developer-mode form editing and default context values.
3. Attempt to close a chantier with open material requests, incomplete controlled documents, or other configured blockers.
4. Resolve blockers and close the chantier; attempt reopening without a reason.

Expected: record rules and model checks deny unauthorized access and workflow bypasses; closeout lists blockers; reopening requires manager authority and a reason.

## Sign-off criteria

Pass only when every applicable workflow has evidence, no unauthorized action succeeds, totals reconcile to the relevant stock/accounting records, and all discovered defects are fixed or formally accepted with an owner and due date.
