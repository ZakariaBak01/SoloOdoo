# EL MOKRIF Odoo 17 Current-State Audit

**Audit date:** 7 September 2026  
**Database inspected:** `TestData`  
**Guide compared:** `EL_MOKRIF_Odoo17_Implementation_Guide (1).pdf`, edition 1.0  
**Overall conclusion:** the chantier, site-stock, and sales-to-chantier foundations are usable for controlled pilot testing. The guide's complete business application is not delivered. Procurement, quality, finance completion, CRM, HR, documents, calendar, dashboards, migration, and role-based readiness remain open.

## Evidence reviewed

- Four custom addons, 35 Python files, 17 XML files, and 47 test methods.
- Deployed `TestData` module registry and the running Odoo HTTP service.
- Custom models, access controls, record rules, views, migrations, and tests.
- The guide's architecture, functional areas, operational pilots, acceptance catalogue, and roadmap.

Static checks run on 7 September 2026:

```text
Python compileall: PASS
XML parse: PASS (17 files)
Odoo service: HTTP 200
```

The disposable clean-database system-test runner was rerun after the latest workflow fixes. It builds the image, installs the custom modules and dependencies, runs post-install tests, and removes the test database. The current source contains 47 test methods. Browser behaviour, email delivery, portal signing, barcode scans, and external integrations are not browser-automated.

## Production state

| Module | State in `TestData` | Version | Purpose |
| --- | --- | --- | --- |
| `elmokrif_chantier` | Installed | `17.0.1.8.0` | Chantier master data, lifecycle, analytic/site initialization, access rules. |
| `elmokrif_chantier_stock` | Installed | `17.0.1.4.0` | Material requests and chantier stock movements. |
| `elmokrif_sale_chantier` | Installed | `17.0.1.0.0` | Sales-order, invoice, and chantier bridge. |
| `elmokrif_integration_tests` | Uninstalled by design | — | Test-only addon, used in disposable test databases. |

The service container and PostgreSQL container are running. The only active human account in the inspected database is `zakariasurface@outlook.com` (`Administrator`). It holds the Chantier User and Chantier Manager roles.

## Delivered functions

### Chantier foundation

`elmokrif_chantier` implements the guide's project-based chantier design:

- `project.project` is extended with chantier flag, immutable reference, customer, company, manager/team, planned dates, work type, region, site address, and lifecycle state.
- Approval creates/reuses one account in the dedicated **Chantiers** analytic plan and one internal site stock location.
- Initialization uses row locking and is idempotent: repeat execution does not create duplicate analytic accounts or locations.
- Lifecycle is enforced server-side: Draft → Approved → In Progress → On Hold → Completed → Closed.
- Invalid direct state writes, cross-company links, manual system-link replacement, deletion, and unauthorized master-data edits are rejected.
- Reopening requires a reason and writes an audit message. Closed chantiers can be archived instead of deleted.
- Open tasks, remaining site stock, open material requests, and linked open sales orders block closure where the applicable addon is installed.

Recent production corrections made new records usable:

- Chantier managers receive the editability default when the New Chantier form opens.
- New chantiers receive the active company before warehouse-domain evaluation, so **My Company** is selectable.
- Timesheet-created analytic accounts are adopted as the chantier account during form creation instead of blocking initialization.

### Material and site-stock workflow

`elmokrif_chantier_stock` implements the guide's site-transfer and consumption portion:

1. Create a material request for an in-progress chantier.
2. Submit and approve it.
3. Generate an Internal Transfer from the supplying warehouse's `Stock` location to the chantier site location.
4. Validate full or partial delivery.
5. Record consumption, return to warehouse, or missing material.
6. Review remaining site stock and current-cost estimate.

Controls implemented:

- Request company and chantier access rules.
- Manager-only request approval and transfer creation.
- Duplicate transfer prevention through row locking.
- Exact move-to-request-line linkage, including separate lines for the same product.
- Delivered status based on completed quantities, including short deliveries without a backorder.
- Warehouse transfer destinations and sources are derived from the chantier operation.

The latest stock fix addresses the manual-transfer issue seen during testing. Once a chantier is selected, the form automatically selects the warehouse's Internal Transfer type and derives locations:

| Chantier operation | Source | Destination |
| --- | --- | --- |
| Delivery to Site | Warehouse `Stock` | Chantier site stock location |
| Return to Warehouse | Chantier site stock location | Warehouse `Stock` |
| Consumption | Chantier site stock location | Inventory adjustment location |
| Missing Material | Chantier site stock location | Inventory adjustment location |

The operation type and locations are read-only after chantier selection. The preferred operational path remains the Material Request form because it provides approval and traceability.

### Sales-to-chantier bridge

`elmokrif_sale_chantier` is installed and available in the Sales application:

- A quotation/order and its lines can link to an existing chantier.
- Customer and company compatibility are validated on server-side create/write/confirmation.
- Confirmation requires an initialized chantier in a commitment-accepting state.
- Sending the first quotation creates one J+3 follow-up activity; repeated sends do not duplicate it; confirmation/cancellation clears it.
- The chantier and analytic allocation propagate from sale lines to invoice lines.
- The chantier cannot be changed on a confirmed order.

The bridge is installed, but a complete production-browser acceptance run has not yet been recorded. Portal signature, actual email delivery, payment collection, and bank reconciliation are outside this addon.

## Guide comparison

| Guide area / acceptance item | Status | Audit finding |
| --- | --- | --- |
| Core data architecture | Partially implemented | The chantier/project, analytic account, site location, sales order, stock picking, and invoice link are implemented. Purchase, document-management, and full accounting designs are absent. |
| `CORE-01`: one project/account/location | Implemented and tested | Initialization is idempotent and guarded against company/link inconsistencies. |
| Company and access configuration | Partially implemented | Chantier user/manager and company/assignment rules exist. Company legal data, languages, 2FA, six pilot roles, least-privilege setup, portal/export/attachment checks, and real-role tests are not evidenced. |
| Contacts and product master data | Standard only / not accepted | No custom ICE/RC checks, import mapping, data-quality workflow, vendor-price policy, or master-data acceptance evidence. |
| Accounting configuration | Not implemented | No confirmed Moroccan localization, chart/journals/taxes/valuation review, payment terms, lock dates, or accountant acceptance suite. |
| Analytic plan and allocation | Partially implemented | The Chantiers plan/account is created; sales-to-invoice allocation is implemented. Type-of-work analytic dimension, applicability rules, and historical consumption-cost accounting policy are absent. |
| Bank matching, reminders, cheques | Not implemented | No statement import/reconciliation, reminder policy, cheque workflow, or finance tests. |
| CRM | Not implemented | No lead/opportunity qualification, targets, site visits, or CRM reporting. The J+3 quotation activity is implemented in the sales bridge only. |
| Sales and order processing | Partially implemented | Chantier quote/order/invoice bridge and J+3 activity exist. Templates, pricelists, portal signature acceptance, down payments/progress billing, credit-note, collection, and sales reporting are absent. |
| Purchase requisitions and approvals | Not implemented | No request-to-RFQ/PO workflow, supplier comparison, 9,999/10,000/10,001 MAD threshold, segregation of duties, or reapproval logic. |
| Receiving quality | Not implemented | No Input/Quality/Quarantine inspection and release gate, partial pass/reject, reversal, or quality-role security. |
| Inventory and replenishment | Partially implemented | Site transfer/consumption/returns/missing workflow exists. Receipt routes, lots/serials, barcode/scanning, reorder rules, supplier returns, replenishment, and valuation reconciliation are absent. |
| `STK-02`: transfer/consume/return | Implemented for current scope | Delivery, partial delivery, consumption, return, missing material, and zero-site-balance closeout behavior have model tests. |
| `STK-01`, `STK-03`, `STK-04` | Not implemented | No supplier receipt/return test, concurrent consumption/overconsumption design, or reorder test. |
| HR and confidentiality | Not implemented | No employee/contract/leave/recruitment/appraisal workflow or HR attachment restriction suite. |
| Documents | Not implemented | No centralized GED, versioning, expiry, search, workspace permission design, or `DOC-01`. |
| Discuss/email | Partially available through Odoo standard | Chatter and activities are used. Inbound/outbound routing, templates, external reply/internal-note control, and `COM-01` are not implemented. |
| Calendar | Not implemented | No business-event links, cancellation/reschedule policy, provider synchronization, or `CAL-01`. |
| Dashboard and KPIs | Not implemented | No agreed eight-KPI definitions, permission-aware dashboard, drill-down, or `KPI-01`. |
| Migration, training, handover | Not implemented | No approved mapping, reconciliation evidence, configuration register, SOP package, or role-training record. |

## Workflow readiness

| Workflow | Readiness | Use conditions |
| --- | --- | --- |
| Create, approve, initialize, start, complete, close a chantier | Ready for pilot | Use complete master data; resolve tasks, stock, requests, and sales-order blockers before close. |
| Warehouse-to-site material issue | Ready for pilot | Create the request in **Material Requests**, approve it, generate the transfer, then validate it. |
| Manual chantier stock operation | Ready for controlled use | Select the chantier and operation; Odoo derives the Internal Transfer and locations. |
| Quotation to chantier invoice | Ready for pilot | Use the same customer and an initialized, in-progress chantier. Perform a browser acceptance run before commercial use. |
| Purchase to quality-approved stock receipt | Not ready | The required purchase and quality modules/workflow do not exist. |
| Financial close, payments, reporting | Not ready | Core guide controls and accountant validation are missing. |

## Findings and risks

### High priority

1. **The purchase and mandatory quality workflow is missing.** The guide requires purchase approvals, receipt traceability, and inspection/release before material can be issued to a chantier. The current Material Request starts from already available central stock. Do not present it as a substitute for procurement control.
2. **Finance readiness is not established.** There is no evidence of Moroccan localization review, taxes, journals, inventory valuation setup, payments, bank matching, financial reports, or accounting closeout controls. Do not use the system as the financial system of record until this is delivered and approved by an accountant.
3. **Production role testing is incomplete.** Only the Administrator account is active in `TestData`. Guide acceptance requires actual buyer, approver, storekeeper, quality approver, salesperson, accountant, HR manager, and employee accounts. Administrator testing is insufficient evidence for permission readiness.

### Medium priority

1. **Material cost is an estimate.** Current site cost multiplies completed consumed/missing quantities by the product's current standard price. A later standard-price change affects the displayed historical estimate. It is not the guide's approved stock-valuation or recognized-cost reconciliation.
2. **Sales browser acceptance is still required.** The bridge code is installed and covered at model level, but the quotation send, J+3 activity, confirmation, invoice, customer permissions, and line-level allocation should be demonstrated in the UI by a salesperson/accountant role.
3. **The stock workflow has no receiving-quality gate.** Central warehouse quantities can be issued after they exist in stock; the guide requires quality-approved receipts before release.
4. **The test suite is model-level.** It does not automate browser rendering, email provider delivery, portal signature, barcode scans, payment gateway, bank import, or external calendar/document systems.

### Low priority

1. The prior review report under `reports/2026-09-07-system-review/` is historical and does not include the newest deployed module versions or the manual-transfer and Sales-bridge deployment changes. This audit supersedes its production-state section.
2. The custom source uses carefully scoped `sudo()` calls for system-owned analytic accounts, locations, request delivery state, and locking. Existing tests exercise key access boundaries, but new modules should continue this review pattern.

## Recommended delivery order

1. **Complete a real-role pilot of the implemented scope.** Create named pilot users: chantier manager, chantier user, salesperson, storekeeper, and accountant. Run the chantier, stock, and sales checklists without Administrator.
2. **Implement Purchase and Quality.** Add chantier purchase requests, buyer/approver segregation, strict 10,000 MAD threshold behavior, RFQ/PO traceability, receipts, inspection/release/reject, supplier return, and quality-access controls. Execute guide Pilot A.
3. **Define and implement the accounting foundation.** Accountant-approved Morocco localization, charts, taxes, journals, payment terms, inventory valuation, analytic applicability, payment/reconciliation and core reports.
4. **Complete CRM and sales billing.** Add opportunity/site-visit workflow, quotation templates/pricing, agreed billing method, down payments or progress billing, credit-note, and collection acceptance tests. Execute guide Pilot B.
5. **Build the remaining business areas.** HR, documents, communication, calendar, dashboards, migration/reconciliation, SOPs, training, and final role-based acceptance evidence.

## Immediate manual acceptance checklist

1. Create a complete chantier, approve/initialize it, refresh, and confirm analytic account plus site location.
2. Start it, submit and approve a Material Request, create the generated Internal Transfer, and validate it.
3. Confirm site stock increased; consume, return, and report missing quantities; confirm site balance and closure blockers react correctly.
4. Create a sales quotation for the same customer, select the chantier, send it, verify one J+3 activity, confirm it, and create an invoice.
5. Repeat the four flows with non-administrator pilot users once those users have been created.

The system should be described as a **chantier-and-site-stock pilot with a sales bridge**, not as a completed implementation of the full guide.
