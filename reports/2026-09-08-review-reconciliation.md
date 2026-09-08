# EL MOKRIF Odoo 17 review reconciliation — 8 September 2026

> Superseded by `2026-09-08-final-review.md`. The later review expanded the suite to 90 server/model tests plus one browser acceptance test, repaired additional security and workflow defects, and distinguishes automated passes from partial and configuration-dependent acceptance cases.

## Current decision

The 6 and 7 September reports describe the repository at the time they were written. Their statements that procurement, quality, CRM, controlled documents, calendar linkage, finance operations, finance readiness, and the management dashboard were not implemented are now stale. Those addons exist in the current worktree and install on a clean Odoo 17 database.

HR is deliberately excluded because it is being developed in another repository.

The expanded validation found and repaired real workflow-integrity defects that the earlier reviews did not cover:

- client-supplied context flags could imitate internal chantier, purchase, quality, finance-readiness, document, stock-consumption, bank-import, reminder, and cheque workflows;
- several readonly workflow-evidence fields could still be forged through ORM/RPC create operations;
- approved consumption completed its stock transfer but failed while recording the source stock-move link;
- approved quality lines were mutable through direct model writes;
- controlled consumption lines remained editable after submission;
- bank imports and matching needed stronger immutability, duplicate, finite-amount, and exact-match controls;
- cheque numbers and collection-hold release needed stronger audit controls;
- CRM qualification accepted a zero contract value;
- calendar site-visit creation did not enforce the salesperson role;
- dashboard initialization did not reliably cover existing and newly created companies.

These paths now use server-private identity tokens and model-level checks. Public context values cannot reproduce those tokens.

## Historical finding reconciliation

| Historical finding | Current result |
| --- | --- |
| Site A stock can reserve Site B delivery | Fixed and regression-tested. Site locations sit outside the warehouse Stock subtree. |
| Chantier Manager lacks required inventory access | Fixed and tested with a manager who is not an Inventory Administrator. |
| Start can leave a chantier uninitialized | Fixed. Approval initializes the foundation and Start repairs missing legacy links. |
| Direct state writes bypass chantier or request rules | Fixed at model level and tested through direct writes. Internal bypass contexts are now unforgeable. |
| Global Material Request has no selectable chantier | Fixed by independent active-company defaults and company consistency checks. |
| Request receipts include other requests | Fixed through exact request-line/move allocation. |
| Backorders lose chantier/request links | Fixed and regression-tested. |
| Material requests leak across companies | Fixed with company and assignment record rules. |
| UoM conversion is missing from quantities/cost | Fixed and tested. |
| Negative request quantities can be approved | Fixed with server-side positive-quantity validation. |
| Material cost changes when standard price changes | Fixed for completed stock effects by using historical stock valuation layers. |
| Purchase requisition/approval is absent | Implemented: shortage procurement, request/PO traceability, company-currency threshold, 9,999/10,000/10,001 behavior, two-person approval, and reapproval invalidation. |
| Mandatory receiving quality is absent | Implemented: Input → Quality → Stock/Quarantine, partial accept/reject, lot preservation, supplier return, role checks, and bypass protection. |
| CRM qualification/site visit is absent | Implemented and now scenario-tested. Standard CRM stages remain configurable master data. |
| Controlled documents are absent | Implemented: company access, review/approval, immutable approved revisions, attachment preservation, expiry activity, archive, and tests. |
| Calendar business links are absent | Implemented for opportunity site visits and chantier/document links; external provider synchronization remains configuration. |
| Dashboard is absent | Implemented with one record per company, permission-aware ORM domains, matching drilldowns, and initialization tests. |
| Bank matching/reminders/cheques are absent | Implemented as controlled CSV import/review, exact payment matching, reminder queue/status workflow, collection holds, and cheque print/void controls. |
| Finance readiness is absent | Implemented as technical checks plus an accountant-approved evidence checklist that gates chantier invoice posting. |

## Flow coverage now present

- Chantier master data, approval, initialization, start, hold/resume, complete, close, reopen, archive, and closeout blockers.
- Company and chantier-assignment isolation with restricted users.
- Warehouse-to-site request, partial delivery/backorder, duplicate product lines, UoM conversion, consumption, returns, loss, stock isolation, and historical material cost.
- Stock/purchase shortage split, vendor-linked PO, approval threshold boundary, two-person approval, and edit-triggered reapproval.
- Supplier receipt, Input-to-Quality routing, inspection, partial acceptance, quarantine, lot traceability, and rejected supplier return.
- Quotation/order/invoice chantier propagation, customer checks, analytic allocation, and finance-readiness posting gate.
- Controlled document submit, approve, revise, supersede, attachment preservation, archive/expiry mechanics.
- Two-person approved material consumption with exact site-stock movement and source audit link.
- CRM qualification and salesperson-created calendar site visit.
- Bank CSV import, within/across-file deduplication, immutable source lines, review and close.
- Dashboard creation for installed and newly created companies.
- Cross-module quote → invoice → materials → closeout scenario.

## Validation evidence

The clean runner installs 12 EL MOKRIF addons plus their Odoo dependencies, 97 modules in total, on a disposable database. The final run after all workflow and quality-routing hardening executed 71 tests with zero failures and zero errors.

```text
71 post-tests
0 failed, 0 errors
```

`git diff --check` passes. Static parsing passes for 107 Python files and 52 XML files. Odoo's clean module installation validates Python imports, model registry construction, data files, access CSVs, XML views, reports, scheduled actions, hooks, and SQL constraints.

## Work that still requires configuration or external acceptance

These items cannot be completed truthfully from repository code alone:

- company legal identity and production ICE/RC values;
- accountant approval of the Moroccan chart, taxes, fiscal positions, journals, payment methods, lock dates, stock valuation accounts, and opening balances;
- actual mail servers, aliases, templates, external replies, delivery results, and reminder recipients;
- real bank CSV layouts and a pilot reconciliation against the chosen bank export;
- Google/Microsoft calendar provider credentials and synchronization;
- portal quotation signature/payment acceptance in the deployed public URL;
- barcode hardware, labels, scanners, and warehouse operator acceptance;
- product, supplier, customer, opening-stock, and opening-balance migration plus source-to-Odoo reconciliation;
- production role assignment, 2FA policy, least-privilege review, backup/restore drill, training, SOPs, and handover evidence.

## Remaining product decisions before more code

The guide mentions functions whose exact accounting or operational policy is not defined sufficiently for a safe generic implementation:

- progress billing, retention percentages, retention release, and their tax/accounting treatment;
- CRM targets, target periods, ownership, and escalation rules;
- supplier-comparison scoring and required quotation evidence;
- replenishment minimum/maximum quantities, lead times, preferred suppliers, and which locations/products are controlled;
- calendar cancellation/reschedule deadlines and escalation behavior;
- cheque voiding after posting, including whether to reverse, cancel, or replace the accounting payment.

Odoo already supplies quotation templates, pricelists, down-payment invoices, credit notes, reorder rules, portal signing, barcode interfaces, calendar synchronization, and accounting reports. These need approved configuration and acceptance data; custom code should be added only where the agreed EL MOKRIF policy differs from standard Odoo.

## Release limit

Passing automated tests establishes the covered model, security, stock, accounting-link, and clean-install behavior. It does not establish that the current worktree has been upgraded into the production database, or that external providers, real master data, browser rendering, concurrency under production load, and every pilot role have passed UAT.
