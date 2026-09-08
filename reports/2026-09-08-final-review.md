# EL MOKRIF Odoo 17 final code review — 8 September 2026

## Verdict

The current worktree is substantially ahead of the 6–7 September reports. All 12 non-HR EL MOKRIF business addons install together on a clean Odoo 17 database, and the current server/model suite passes 90 tests with no failures or errors. HR remains outside this repository by instruction.

This is strong code-level evidence for the covered workflows. It is not production acceptance: the live `odoo17` database was not upgraded, production data was not migrated, and external email, portal, bank, calendar-provider, accounting-policy and hardware acceptance remain outstanding.

## Defects found and repaired in this review

- Material requests could be created directly in submitted, approved or done states. Submitted requests also allowed line insertion, reparenting and deletion. Creation and all line mutations are now limited to draft, requester identity is protected, and non-finite quantities are rejected.
- Public Odoo `default_*` context values could bypass several create-time checks. Protected workflow state, evidence and source-link defaults are now rejected or overwritten with safe values across chantier, purchasing, quality, documents and finance operations.
- A new chantier could repurpose an analytic account already attached to another project or containing analytic entries. The form-compatible account adoption path now checks access, company, existing project/chantier ownership and analytic use.
- Purchase orders could be created already confirmed and critical buyer/header or line changes needed stronger reapproval and immutability controls.
- Quality inspection source quantities and receipt/product links could be altered; inspection lines could be injected or reparented; protected Input/Quality locations could be bypassed through move-level locations; quality backorders could lose routing evidence. These paths are now guarded and audit records retained.
- Consumption evidence, request ownership and submitted line contents needed stronger create/write/reparent/delete protection. Approval uses row locks and exact stock movement links.
- Bank matching ignored payment direction and journal currency and allowed payment reuse; malformed/non-finite CSV amounts were insufficiently rejected; deleting the parent import could bypass line audit retention. Matching and import retention now enforce these invariants.
- Reminder email could be delivered after a collection hold but before the status cron ran, while a later refresh could overwrite already-sent evidence. Delivery-time eligibility and sent-state precedence are now enforced.
- Cheque reports could be rendered outside the controlled action and void evidence could be changed. The report, payment and void trail are now guarded. A broken SQL unique constraint that referenced delegated `account.payment.company_id` now uses a stored payment-table company column.
- Approved controlled-document files and workflow evidence could be edited, relinked or made public. Attachment access is checked before binding, approved/reviewed evidence is immutable, revisions own independent attachments, and concurrent successors are prevented by a unique predecessor.
- Opportunity-to-quotation handoff did not preserve an explicitly selected chantier. Calendar events lacked a company rule, dashboard sales omitted part of the selected day, and dashboard computation failed hard when a user lacked a source-model ACL. These paths now preserve context, isolate companies and report unavailable indicators.
- The test scripts shared the running database server, reused fixed container names and deleted caller-selected databases. Both suites now create UUID-named private networks and disposable PostgreSQL/Odoo containers with generated credentials, no published ports and no production volumes. Logs and browser artifacts are retained and a zero-test run is rejected.

## Guide acceptance status

| Guide ID | Current evidence | Status |
| --- | --- | --- |
| SEC-01 | Company/assignment rules and forbidden-role tests cover chantiers, requests, controlled documents, calendar records and dashboard aggregates. | Partially automated; a full UI/export/direct-link matrix for every role still needs UAT. |
| SEC-02 | HR was deliberately excluded. | Not assessed here. |
| CORE-01 | Repeated initialization, lifecycle transition, legacy repair and system-link tests pass. | Automated pass. |
| CRM-01 | Qualification, site-visit creation, chantier quotation handoff and J+3 activity creation/closure are covered. | Partial; repeated scheduled-job and external mail acceptance remain. |
| SAL-01 | Browser flow covers salesperson quotation send, confirmation and multi-chantier line visibility; ORM assertions cover resulting state and invoice allocation. | Partial; public portal signature/payment and an additional-order scenario remain. |
| SAL-02 | Odoo standard down-payment/credit features are available, but the guide's advance/final/credit scenario was not executed here. | UAT required. |
| PUR-01 | 9,999/10,000/10,001 MAD boundary and company-currency behavior are covered. | Automated pass. |
| PUR-02 | Self-approval, approval evidence and post-approval edit guards are covered. | Automated pass. |
| QUA-01 | Input → Quality, partial acceptance/rejection, lot preservation, quarantine and direct bypass are covered. | Automated pass for the implemented scope. |
| STK-01 | Partial receipt, backorder link, accepted quantity and rejected supplier return/source links are covered. | Automated pass for the implemented scope. |
| STK-02 | Site transfer, approved consumption, valuation source and closeout totals are covered. | Partial; an explicit unused-material-return reconciliation scenario remains. |
| STK-03 | Row locking, unique source links, retry guards and insufficient-stock checks exist. | Partial; true parallel-transaction stress testing remains. |
| STK-04 | Available-stock/procurement splitting and duplicate planning prevention are covered. | Partial; standard reorder-rule incoming-supply/order-multiple acceptance requires configured master data. |
| FIN-01 | Exact existing-payment matching now checks sign/direction, currency, amount/reference and single use. | Partial; partial payments, bank fees, grouped payments and ambiguous candidate review need real bank samples and accountant UAT. |
| FIN-02 | Within-file and across-file reimport deduplication are covered. | Automated pass for the supported CSV format. |
| FIN-03 | Delivery-time collection-hold suppression and immutable sent evidence are covered. | Partial; production templates, recipients and actual SMTP results remain. |
| FIN-04 | Finance readiness gates and chantier analytic propagation are covered. | Partial; chart, taxes, journals, reports, balances and allocations need accountant reconciliation. |
| HR-01 / HR-02 | Owned by the separate HR repository. | Excluded. |
| DOC-01 | Review/approval/revision, attachment retention/privacy, access and expiry evidence are covered. | Partial; search/workspace usability and real-role UAT remain. |
| COM-01 | Chatter and activities are used. | Not accepted; incoming routing and external-reply/internal-note behavior require configured mail infrastructure. |
| CAL-01 | Opportunity visit links and company isolation are covered. | Partial; reschedule/cancel policy and Google/Microsoft synchronization remain. |
| KPI-01 | Eight guide KPIs, permission-aware computation and matching drilldowns are implemented. | Partial; management/accountant reconciliation of every metric against representative source reports remains. |

## Validation evidence

- Clean install and server/model tests: `90 post-tests`, `0 failed, 0 errors`, 97 installed modules. Evidence: `reports/test-artifacts/system/20260908-145120-1df8aa03/odoo.log`.
- Browser acceptance: `1 post-test`, `0 failed, 0 errors`. The browser sends and confirms a multi-chantier quotation as the salesperson, then posts its invoice as the accountant; ORM assertions verify the resulting states and allocation. Evidence: `reports/test-artifacts/browser/20260908-150107-2a14de11/odoo.log`.
- Static checks: 109 Python files compile; 53 XML files parse; the shared PowerShell runner parses; `git diff --check` passes.
- Secret/public-endpoint scan: no custom HTTP controllers were found and no embedded production credential was found outside the intentionally excluded local `.env`. Browser-only test passwords are generated test-user values in disposable databases.

## Work still requiring configuration, policy or external acceptance

- Confirm company identity, ICE/RC, languages, currencies and production users; assign least-privilege roles and enforce the chosen 2FA policy.
- Accountant approval and reconciliation of Moroccan localization, chart, taxes, fiscal positions, journals, payment methods, lock dates, stock valuation accounts, opening balances and financial reports.
- Product/contact/vendor cleanup, stable external IDs, opening stock/balance migration and source-to-Odoo reconciliation.
- Real bank export mapping and pilot reconciliation, including fees, partial/grouped payments and ambiguous cases.
- SMTP/incoming aliases, external replies, reminder recipients and delivery evidence; Google/Microsoft calendar credentials and conflict behavior.
- Portal signature/payment acceptance on the deployed public URL; barcode scanners/labels and operator acceptance.
- Role-based UAT, performance/concurrency exercise, backup/restore drill, training, SOPs and handover evidence.

Further custom code needs an approved business rule before implementation for progress billing/retention, CRM target periods, supplier-comparison scoring/evidence, reorder min/max/multiples, calendar escalation deadlines and the accounting treatment of a voided posted cheque. Implementing a generic rule now would encode an unapproved financial or operating policy.

## Reconciliation of earlier reports

The concrete defects in the 6 September review are repaired and regression-covered. The 7 September reports were correct descriptions of the smaller codebase at that time, but their “not implemented” statements for purchasing, quality, CRM, controlled documents, calendar links, dashboard, bank operations, reminders, cheques and finance readiness are stale. This report supersedes the broad “all flows implemented” wording in `2026-09-08-review-reconciliation.md`: several guide acceptance cases remain partial or require real configuration and business sign-off as listed above.
