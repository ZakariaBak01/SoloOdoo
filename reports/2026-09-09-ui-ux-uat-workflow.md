e# EL MOKRIF Odoo 17 UI, UX and Business-Flow UAT Playbook

**Purpose:** Validate that the application is usable, secure and operationally correct for real EL MOKRIF users.

**Test scope:** Company setup, chantier, estimation, CRM, sales, purchasing, quality, stock, consumption, accounting, bank import, collection, cheques, documents, calendar, HR, dashboard and chantier closeout.

**Rule:** Test with named role accounts. Do not accept a workflow demonstrated only with the administrator account.

## 1. Result and evidence standard

Record each test using this result:

| Field | Value |
| --- | --- |
| Test ID |  |
| Tester and role |  |
| Date and database |  |
| Browser/device |  |
| Result | Pass / Fail / Blocked / Not applicable |
| Actual result |  |
| Record references |  |
| Screenshot/video |  |
| Defect ID |  |
| Severity | Critical / High / Medium / Low |
| Retest result |  |

A test passes only when:

- the intended user can find and complete the action without administrator help;
- totals and states match the expected result;
- forbidden users cannot perform the action through the UI, direct URL, import or developer mode;
- the user receives a clear, actionable error when an action is rejected;
- the resulting chatter, activities and linked records provide a usable audit trail.

## 2. Test environment and personas

Use a copied or disposable acceptance database. Do not run destructive tests on production.

Create these named users without Settings/technical administration access:

| User | Role | Required access |
| --- | --- | --- |
| U1 | Management / Chantier Manager | Chantier Manager, dashboard, designated approvals |
| U2 | Chantier User | Assigned chantier operations only |
| U3 | Buyer | Purchase User and Chantier Purchase Buyer |
| U4 | Purchase Approver | Purchase approval group; different person from U3 |
| U5 | Storekeeper | Inventory User; no quality approval |
| U6 | Quality Inspector | Quality Inspector; no purchase or accounting approval |
| U7 | Salesperson | Own/team CRM and Sales records |
| U8 | Accountant | Accounting Administrator for UAT |
| U9 | Document User | Assigned controlled documents only |
| U10 | Document Manager | Review, approve and revise documents |
| U11 | Employee | Own HR requests and appraisal only |
| U12 | HR Officer/Manager | HR workflow and confidential records |
| U13 | Dashboard User | Management KPIs without broad operational access |
| U14 | Other-company User | Company B only; used for isolation tests |

Create two companies:

- **Company A:** EL MOKRIF COMPANY SARL, Morocco, MAD.
- **Company B:** a clearly labelled UAT isolation company.

Create reusable test records:

- Customer `UAT Customer A` and a separate Company B customer.
- Supplier `UAT Supplier A`.
- Storable products: Cement Bag, Steel Bar and Paint Bucket.
- Service product: Construction Service.
- Units: unit, kg and 50 kg bag with valid conversions.
- Warehouse `WH-A` with enough Cement for partial stock fulfilment.
- Taxes, journals, accounts, payment methods and analytic settings approved by U8.
- One CRM opportunity worth 30,000 MAD.
- One employee connected to U11 and managed by U12.

## 3. UX checks applied to every workflow

For every screen, record defects when any answer is No.

| UX check | Expected result |
| --- | --- |
| Discoverability | The user finds the record/action from a logical menu or smart button. |
| Terminology | Labels use business language consistently: chantier, request, inspection, consumption and approval. |
| Required data | Required fields are visible before the user attempts the action. |
| Defaults | Company, chantier, warehouse, customer, currency and dates default correctly. |
| Domains | Selectors show only valid company, customer, chantier, warehouse and source records. |
| State clarity | The current state and the next permitted action are obvious. |
| Button control | Users see only actions appropriate to their role and record state. |
| Error quality | Errors explain what is wrong and how to correct it. |
| Audit trail | Approval, rejection, reopening and generated records are traceable. |
| Navigation | Smart buttons open the exact linked records with matching counts. |
| Data entry | The same operational fact is entered once. |
| Responsiveness | Site operations remain usable at 390 px mobile width and 768 px tablet width. |
| Accessibility | Fields have labels, keyboard focus is usable, and status is not communicated by colour alone. |
| Performance | Normal lists/forms open within 3 seconds on the UAT environment; actions give feedback during longer work. |

## 4. Execution sequence

Execute the workflows in order. Later scenarios reuse records and evidence from earlier ones.

### UAT-00 — Login, menus and role landing pages

1. Log in separately as every persona.
2. Record the visible applications and first landing page.
3. Search for Chantier, Material Request, Quality Inspection, Construction Estimate and Dashboard.
4. Confirm that each role sees only relevant menus.
5. Confirm U14 cannot select Company A.
6. Repeat one site-user check on mobile width.

Expected:

- no operational role sees Settings or unrelated confidential applications;
- menu names are understandable without technical model knowledge;
- no empty or access-error menu is displayed;
- switching company refreshes domains, defaults and dashboard values.

### UAT-01 — Chantier creation, approval and initialization

1. As U2, attempt to create a chantier.
2. As U1, create `CH-UAT-001` with Company A but leave one required field empty.
3. Confirm Customer lists registered customers only and Site Address lists physical Delivery/Other addresses only.
4. Confirm Chantier Manager lists U1 only for Company A. Confirm Chantier Team lists the same-company chantier workflow users U2, U3, U4 and U6, with no unrelated internal or Company B accounts.
5. Confirm the chantier Settings page does not show the inbound-email alias control; task responsibility is assigned on tasks and through the chantier team.
6. Try **Approve and Initialize** and read the validation message.
7. Complete customer, manager, site address, dates, region, work type and warehouse.
8. Approve and initialize.
9. Confirm exactly one analytic account and one internal site location were created and the chatter contains the internal initialization audit note. The account and plan names are verification-only values for U1 and must not open accounting records.
10. Run initialization again.
11. Open all smart buttons and compare counts with their lists.
12. As U14, try the copied direct URL for `CH-UAT-001`.

Expected:

- only U1 can create/approve;
- manager and team selectors are limited by chantier role and active company;
- project favorites never grant chantier or linked-record access;
- the incomplete dossier is blocked with missing fields listed;
- approval/initialization succeeds even when outbound mail is not configured;
- repeated initialization creates no duplicate account or location;
- links use Company A and remain visible to assigned users only;
- U14 receives access denied and no identifying data is exposed.

UX focus: Use a single primary approval action. Treat any separate initialization action as a recovery tool for managers.

### UAT-02 — Estimate, approval, revision and variance

1. Open Estimates from the chantier smart button.
2. Create a Draft estimate with dimensions, material ratios, unit costs, labour productivity, machinery, transport, contingency, tax and phase percentages.
3. Enter invalid values: zero dimension, negative cost, phase total other than 100 and progress above 100.
4. Correct the values and submit.
5. As U2, attempt approval; then approve as U1.
6. After approval, attempt to change every budget driver.
7. Create a revision and leave it Draft.
8. Confirm the previous approved estimate remains the active baseline.
9. Approve the revision and confirm the predecessor becomes Superseded.
10. Create an overrun and approve a variance with reason and evidence.
11. As an unrelated chantier user, try opening the cost estimate directly.

Expected:

- invalid and non-finite quantities/costs are rejected;
- state and approval evidence cannot be changed directly;
- the approved baseline is fully immutable;
- only one approved baseline exists per chantier;
- a Draft/Rejected revision does not remove the current approved baseline;
- confidential cost details remain limited to assigned operational/management users.

UX focus: Separate **Budget Baseline** from **Actual Costs**. Users should not re-enter daily-report or accounting actuals on the estimate.

### UAT-03 — CRM qualification and site visit

1. As U7, create the 30,000 MAD opportunity for UAT Customer A.
2. Attempt qualification without each required business field.
3. Complete qualification.
4. Create the chantier quotation from the opportunity.
5. Create a site visit, adjust its time and invite the customer.
6. Reschedule and cancel a second visit.
7. Confirm the opportunity, event, customer and chantier links are reciprocal and easy to find.
8. Try selecting Company B records in every selector.

Expected:

- qualification errors identify missing data;
- chosen chantier/customer context is preserved;
- only valid same-company records appear;
- reschedule/cancel behavior does not create duplicate events;
- native event privacy and attendees continue to work.

### UAT-04 — Ordinary and chantier sales

1. As U7, create a normal quotation with no chantier and confirm it.
2. Create a chantier quotation from `CH-UAT-001`.
3. Add lines for Construction Service and materials.
4. If line-level allocation is enabled, allocate lines to more than one chantier.
5. Add a second analytic dimension and verify the chantier default does not erase it.
6. Send the quotation and verify the customer-facing PDF/email/portal view.
7. Run/repeat the J+3 follow-up process and verify one activity only.
8. Confirm the order and verify the activity closes.
9. Create an additional order for the same chantier and confirm no new chantier is created.

Expected:

- an ordinary non-chantier order follows standard Odoo behavior;
- chantier is mandatory only for a declared chantier order;
- customer and company mismatches are blocked;
- analytic dimensions are preserved;
- repeated sends/jobs do not duplicate follow-up activities.

### UAT-05 — Material request and stock/procurement split

1. As U2, create a request from `CH-UAT-001` with Cement and Steel.
2. Add duplicate product lines with different required dates or purposes.
3. Submit; attempt to edit lines afterward.
4. As the requester, attempt self-approval when segregation is enabled.
5. Approve with the authorized role.
6. Confirm available stock and shortage quantities are understandable.
7. Generate the internal transfer for available stock.
8. Generate procurement only for the shortage.
9. Repeat generation and verify no duplicate transfer or procurement is created.
10. Place the chantier On Hold and attempt a new request.

Expected:

- only Draft requests are editable;
- approvals and two-person controls are enforced;
- stock, incoming supply and shortage do not double count;
- request lines retain exact links to transfers and purchase lines;
- On Hold blocks new commitments with a clear message.

UX focus: Present **Available**, **Incoming**, **To Transfer** and **To Purchase** together before approval.

### UAT-06 — RFQ, approval threshold and vendor selection

1. As U3, open the generated RFQ and select UAT Supplier A.
2. Record vendor comparison/rationale and supporting quotation evidence.
3. Test separate POs at 9,999, 10,000 and 10,001 MAD in company currency.
4. Confirm the configured equality, tax basis and currency-conversion rule.
5. Try self-approval as U3.
6. Approve as U4.
7. Change vendor, quantity, price and tax after approval.
8. Confirm approval is invalidated and reapproval is required.
9. Verify standard Odoo Purchase double validation does not create a second contradictory gate.

Expected:

- threshold behavior matches the signed company policy;
- U3 cannot approve their own controlled PO;
- critical changes clear approval evidence;
- the user sees one understandable approval state and one next action.

### UAT-07 — Supplier receipt and quality release

1. As U5, receive 60 of 100 ordered units and create a backorder.
2. Confirm goods enter Input/Quality rather than usable stock.
3. Attempt to bypass Quality by changing destination locations.
4. As U5, attempt quality approval.
5. As U6, record 50 accepted and 10 rejected with reason, condition and specification evidence.
6. Approve and release.
7. Confirm 50 moves to usable stock and 10 to quarantine.
8. Receive the backorder and confirm all chantier/request/PO links remain.
9. Create the supplier return for rejected goods and validate it as U5.

Expected:

- accepted plus rejected equals received quantity;
- storekeeper cannot approve Quality;
- rejected stock cannot be consumed or silently routed to Stock;
- lots/serials and source links remain intact;
- supplier return adjusts receipt/billing quantities according to approved policy.

### UAT-08 — Site transfer, consumption and unused return

1. Validate the central-to-site transfer.
2. Confirm site stock is visible from the chantier.
3. As U2, create a consumption while the chantier is not In Progress.
4. Start the chantier and create the consumption again.
5. Request more than site availability and confirm it is rejected.
6. Submit a valid consumption.
7. Attempt self-approval, then approve with the configured approver.
8. Double-click/repeat approval and verify only one stock effect.
9. Return unused material through a source-linked return action.
10. Compare physical stock and historical valuation with the expected quantities.

Expected:

- consumption is allowed only In Progress;
- every approved consumption produces one exact completed picking;
- retries and concurrent actions do not duplicate stock movement;
- unused return reverses the correct source effect once;
- users assigned to another chantier cannot open the consumption record.

UX focus: Optimize this screen for phone/tablet use with product, available quantity, consumed quantity and submit action visible without horizontal scrolling.

### UAT-09 — Daily reporting and live cost control

1. As U2, create daily reports for labour, equipment, completed work, weather, blockers and photos.
2. Test zero/negative quantities and costs.
3. Complete some chantier tasks and leave others open.
4. Open Live Cost Control.
5. Verify progress derives from completed tasks; use manual progress only when no tasks exist.
6. Confirm daily-report labour/equipment/other costs flow automatically into actual cost.
7. Add stock consumption, purchase commitments, a supplier bill and a customer invoice.
8. Confirm budget, commitment, actual cost, invoiced revenue, collected cash and forecast are separately labelled.
9. Create a customer credit note and confirm it reduces net invoiced revenue.

Expected:

- operational facts are entered once;
- every total drills into its source records;
- credit notes use the correct sign;
- internal stock transfers are not counted as consumption cost;
- warning thresholds are clear and do not confuse spending variance with schedule variance.

### UAT-10 — Finance readiness, invoice, payment and credit

1. As U8, review the Finance Readiness technical checks and checklist.
2. Attempt to approve with missing checks/evidence.
3. Complete and approve readiness.
4. Create a 20% down-payment invoice from the 30,000 MAD order.
5. Verify 6,000 MAD before applicable tax and the chantier analytic allocation.
6. Post, register a partial payment and inspect residual/aging.
7. Create final billing with advance deduction.
8. Create a 1,000 MAD tax-exclusive customer credit note.
9. Confirm net commercial invoicing equals 29,000 MAD in this test example.
10. Change a critical accounting configuration after Finance Readiness approval and attempt another posting.

Expected:

- posting is blocked until readiness is both approved and currently valid;
- standard down-payment and credit-note behavior is preserved;
- journal entries balance and analytic distributions remain complete;
- invoices, payments, residuals and credits reconcile with standard reports.

### UAT-11 — Bank import and real reconciliation

1. Upload a valid sample UTF-8 CSV.
2. Test malformed headers, invalid dates, invalid/non-finite amounts and duplicate rows.
3. Reimport the same file.
4. Test exact, ambiguous, partial, fee-adjusted and grouped payment examples.
5. Confirm an exact suggestion, then complete the match.
6. Open the native bank journal/reconciliation view.
7. Verify the bank transaction and receivable/payable/payment entries are actually reconciled.
8. Close the import only after every line is reconciled, explicitly unmatched or ignored with reason.

Expected:

- duplicates do not create additional transactions;
- ambiguous cases remain for review;
- “Reconciled” means native Odoo accounting reconciliation, not only a custom reference to a payment;
- ignored items retain reviewer, time and reason.

### UAT-12 — Collections, reminders and cheques

1. Make an invoice overdue by 7, 15 and 30 days and run reminder jobs repeatedly.
2. Confirm one reminder per invoice/level.
3. Pay an invoice after its email is queued but before delivery.
4. Put another invoice on collection hold with a reason.
5. Confirm queued mail is suppressed before delivery.
6. Retry a failed reminder as U8.
7. Create a posted outbound cheque payment, assign a cheque number and print it.
8. Try duplicate cheque numbers and reprinting.
9. Void a printed cheque with a reason and verify the accounting treatment follows the approved policy.

Expected:

- paid, reversed, in-payment or disputed invoices receive no reminder;
- reminders and cheque evidence remain immutable;
- cheque “Void” status is not mistaken for cancellation/reversal of its accounting entry.

### UAT-13 — Controlled documents

1. As U9, attach and submit a chantier contract.
2. As U10, reject it with a required reason.
3. Correct and resubmit; approve it.
4. Attempt to replace, relink, delete or make the approved file public.
5. Create a Draft revision and confirm the approved predecessor remains current.
6. Approve the revision and confirm atomic supersession.
7. Set near and past expiry dates, then run the expiry job twice.
8. Search by chantier, category, owner, state and expiry.
9. As an unrelated chantier user and U14, attempt direct document and attachment URLs.

Expected:

- review decisions retain reviewer, date and reason;
- one approved current revision remains available at all times;
- duplicate expiry activities are not created;
- document and attachment access follows chantier/audience scope, not company membership alone.

### UAT-14 — HR privacy and workflows

1. As U11, request leave for self and attempt one for another employee.
2. As U12, approve/refuse/cancel using the configured sequence and required reasons.
3. Create an appraisal; complete self-assessment and manager review.
4. Complete and reopen it with a reason.
5. Run contract-expiry automation twice.
6. Convert a recruitment applicant to employee.
7. Test direct attachment URLs for employee, contract, applicant, leave and appraisal files using unrelated users.

Expected:

- employees see only their permitted HR records;
- approval evidence and completed appraisals cannot be directly edited;
- expiry activities are idempotent;
- confidential attachments cannot be public or token-shared outside policy.

### UAT-15 — Dashboard accuracy and access

1. As U13, open the Company A dashboard for the pilot date.
2. Reconcile each KPI with its source report/list:
   - monthly net invoiced revenue;
   - receivables overdue more than 30 days;
   - quotation conversion for the approved period/cohort;
   - stock value at the effective date;
   - pending supplier orders;
   - awaiting purchase approval;
   - open pipeline and weighted value;
   - current absences;
   - scheduled deliveries;
   - consumed material cost.
3. Open every drilldown and confirm its records reproduce the card value.
4. Switch to Company B.
5. Remove one source-model permission and refresh.

Expected:

- KPI definitions, signs, date ranges and source domains match;
- credit notes and credits do not incorrectly inflate or offset unrelated balances;
- missing permission displays “Unavailable,” not a misleading zero;
- no Company A value leaks into Company B.

### UAT-16 — Closeout, reopen and archive

1. Mark the chantier Completed.
2. Leave one blocker in each area: open task, site stock, request, purchase, quality return, document, invoiceable order, unpaid financial exception and unapproved variance.
3. Attempt closure.
4. Verify a closeout wizard lists every blocker with a working link.
5. Resolve each blocker and reconcile physical/accounting totals.
6. Close as U1.
7. Attempt new operational commitments after closure.
8. Reopen without a reason, then with a reason.
9. Close again and archive.
10. Confirm historical stock, accounting, documents and chatter remain accessible to authorized users.

Expected:

- closure cannot hide unresolved operational or financial work;
- the manager sees a single actionable checklist;
- reopening records user, time and reason;
- archive removes the chantier from ordinary active lists without deleting history.

### UAT-17 — Security and bypass regression

Repeat these checks against chantier, estimate, request, inspection, consumption, document, bank import, readiness, leave and appraisal records:

1. Open a record through a copied direct URL as an unauthorized user.
2. Search and export from list views.
3. Use Favorites and grouped/pivot views.
4. Attempt cross-company selection with both companies enabled.
5. In developer mode, try changing readonly state/evidence fields.
6. Where imports are enabled, try importing state, company, approver and source-link fields.
7. Refresh after access denial and confirm no name, amount, attachment or chatter preview leaked.

Expected:

- server-side enforcement matches button visibility;
- ACL and record rules protect read, write, create and delete separately;
- child lines and attachments inherit the parent security boundary;
- managers receive intended broader access without bypassing company boundaries.

### UAT-18 — Work-package planning and field execution

1. As U1, open **Chantier > Project Control > Work Packages** and create a package for `CH-UAT-001`.
2. Select the current BOQ, WBS section and BOQ scope lines; assign a manager, responsible user, planned dates, quantity, unit and resource budgets.
3. Attempt **Confirm Readiness** while method statement, drawings, permits or materials are not ready.
4. Complete every readiness check and attach the approved method/drawing/permit evidence.
5. Confirm readiness, release the package and start it.
6. Create package tasks and confirm the chantier, bundle, assignee, deadline and priority default correctly.
7. Enter an installed quantity above the planned quantity, then correct it and complete the quantity.
8. Submit completed work for inspection, accept it as U1 and close the package.
9. Create a second package dependent on the first and attempt release before its predecessor closes.

Expected:

- work cannot be released with missing readiness evidence or an open predecessor;
- installed quantity cannot exceed planned scope;
- task and work-package links are reciprocal and retain the same chantier context;
- inspected work follows `Draft → Ready → Released → In Progress → Awaiting Inspection → Accepted → Closed`;
- overdue open packages affect chantier health and block chantier closure.

### UAT-19 — Site issue, RFI and submittal control

1. As U2, record a High site issue with location, responsible user, due date, description and photos.
2. Assign and resolve it; attempt to close it without manager verification.
3. Create an RFI from the issue and confirm the question, chantier, owner and deadline carry across.
4. Submit, review and answer the RFI; record its cost and schedule impact and close it.
5. Create a change event from the answered RFI and confirm source links remain reciprocal.
6. Create a material submittal with specification reference, BOQ line, supplier/contractor, reviewer, deadline and revision file.
7. Try submitting without a file, then submit with evidence.
8. Record **Approved as Noted**, create a revision and confirm the decided revision becomes immutable/superseded.
9. Make an RFI and submittal overdue and refresh chantier health.

Expected:

- field observations can become RFIs or commercial change events without re-entering their origin;
- only verified issues close and every transition is recorded in chatter;
- RFI submitted/answered/closed timestamps cannot be edited directly;
- submittal decisions require comments and approved revisions remain immutable;
- overdue RFIs mark the chantier Off Track and overdue submittals mark it At Risk.

### UAT-20 — Change event and formal variation order

1. Create a change event from the RFI with reason, responsibility, evidence, estimated cost, estimated revenue and schedule days.
2. Attempt submission without evidence.
3. Submit, estimate, commercially review and accept it for variation.
4. Create its variation order twice and confirm only one variation is produced.
5. Add priced variation lines linked to the affected BOQ lines.
6. Submit for internal review and request customer approval.
7. Attempt approval without the customer approval reference and signed evidence.
8. As U1, record the customer reference, approve and compare current budget/current contract with the original values.
9. Select the current approved BOQ and prepare a BOQ revision.
10. Confirm manual quantity deltas appear only on the new Draft BOQ revision; the approved baseline remains unchanged.
11. Approve the BOQ revision through the existing estimator/reviewer/approver segregation and mark the variation implemented.

Expected:

- approved change cost increases Current Budget and approved change revenue increases Current Contract;
- customer and internal approvals retain user, time, reference and evidence;
- an accepted change event converts once and no longer remains in pending-change exposure;
- take-off based BOQ quantities require their take-off evidence to be revised explicitly;
- Draft, rejected or customer-pending variations do not alter approved project totals;
- unimplemented variations block chantier closure.

### UAT-21 — BOQ progress certification, invoicing and project-control dashboard

1. Create a client-contract BOQ with contract rates and approve it through the BOQ workflow.
2. As U1, create a Progress Certificate for a period and load its BOQ lines.
3. Enter previous and current measured quantities; attempt a cumulative quantity above the contract quantity.
4. Set retention and advance recovery, then compare gross, deductions and net current value manually.
5. Attach measurement evidence and submit.
6. Attempt verification as the submitter; verify as a different authorized user.
7. Record the customer certificate reference and approve as a third authorized manager.
8. Create the invoice and confirm one Draft customer invoice is linked to the certificate, chantier and analytic account.
9. Repeat invoice creation and confirm no duplicate invoice is created.
10. Open the chantier **Project Control** tab and reconcile original budget, approved changes, current budget, actual cost, forecast cost, contract value, certified revenue and forecast margin.
11. Open Management Dashboard and reconcile active/At Risk/Off Track chantiers, critical issues, overdue RFIs, pending change exposure, approved variation cost and certified revenue.
12. Switch to Company B and verify every project-control total is isolated.

Expected:

- cumulative certification cannot exceed contracted quantities;
- retention and advance recovery are transparent deductions rather than hidden invoice adjustments;
- submitter, verifier and approver segregation is enforced;
- approved certificates are immutable and create at most one linked invoice;
- project and portfolio figures drill back to the same controlled source records;
- open work packages, RFIs, submittals, changes, variations and certificates participate in closeout checks.

## 5. Exploratory UX session

After scripted testing, give each operational user 30 minutes without instructions and ask them to complete their normal flow. Observe rather than guide them.

Record:

- where they first look for the action;
- labels they misunderstand;
- fields they cannot confidently complete;
- screens requiring unnecessary navigation;
- repeated data entry;
- errors they cannot recover from;
- missing totals or status information;
- actions that feel dangerous or ambiguous;
- mobile problems for site/store users;
- reports or printouts they still create outside Odoo.

Prioritize UX defects that cause incorrect records or off-system work above cosmetic preferences.

## 6. Release gates

| Gate | Required result |
| --- | --- |
| Security | No unauthorized access through UI, export, direct URL or attachment download. |
| Stock | Pilot quantities and valuation reconcile with no duplicate movements. |
| Finance | Entries balance; invoice, credit, payment, bank and aging results reconcile. |
| Approvals | No self-approval or direct state/evidence bypass. |
| Usability | Each role completes its ordinary flow without administrator intervention. |
| Audit | Approvals, rejections, returns, revisions, voids and reopening retain evidence. |
| Integration | Source links survive partial receipts, backorders, credits and returns. |
| Performance | Accepted response times and no failed scheduled jobs. |
| Recovery | Backup/restore and failed-action recovery are demonstrated separately. |

Critical and High defects block the affected workflow. Medium defects require an owner, workaround and agreed resolution date. Low defects may be accepted by the process owner.

## 6.1 Current automated evidence

The isolated Odoo regression harness was run on 16 September 2026 after the UAT-05 fulfillment guard was added:

| Scope | Result | Evidence |
| --- | --- | --- |
| Chantier, stock and purchase/quality workflows | 71 tests passed; 0 failed; 0 errors | `reports/test-artifacts/system/20260916-145857-38b2bd55/odoo.log` |
| Chantier, estimation, tender/BOQ and construction-control workflows | 48 tests passed; 0 failed; 0 errors | `reports/test-artifacts/system/20260916-150118-c734f403/odoo.log` |

These are automated regression results; named-role UI, mobile, attachment and exploratory checks still require execution in the acceptance database.

## 7. Final sign-off

| Area | Owner | Result | Open defects | Signature/date |
| --- | --- | --- | --- | --- |
| Chantier operations |  |  |  |  |
| Estimation and cost control |  |  |  |  |
| CRM and Sales |  |  |  |  |
| Purchase and supplier management |  |  |  |  |
| Inventory and Quality |  |  |  |  |
| Accounting and Finance |  |  |  |  |
| Documents and Calendar |  |  |  |  |
| HR and privacy |  |  |  |  |
| Dashboard and reporting |  |  |  |  |
| Management release decision |  |  |  |  |

The application is ready only when each mandatory flow passes with its real role, master data, configuration, exception paths and reconciled totals.
