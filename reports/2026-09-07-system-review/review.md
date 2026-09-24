# SoloOdoo code, integration, and system-test review — 7 September 2026

## Decision

The implemented scope works together on a clean Odoo 17 database: all custom modules install and the automated suite completes with **44 tests, 0 failures, and 0 errors**.

This does **not** mean the whole implementation guide is complete. The repository currently delivers the chantier foundation, material/site-stock workflow, and the sales-to-chantier bridge. Large guide areas such as purchase, receiving quality, the full CRM pipeline, finance operations, HR, documents/calendar, and management dashboards are not implemented in this repository.

The initial validation used a disposable database that the runner deletes after execution. At the user's later request, `TestData` was backed up and upgraded to `elmokrif_chantier` 17.0.1.5.0 and `elmokrif_chantier_stock` 17.0.1.3.0.

## Code reviewed

- `elmokrif_chantier`: chantier master data, lifecycle, analytic account, site location, role and company rules, task linkage, closure and reopening controls.
- `elmokrif_chantier_stock`: material requests, warehouse-to-site transfers, backorders, consumption, returns, missing material, stock/cost summary, and closeout blockers.
- `elmokrif_sale_chantier`: quotation/order linkage, customer and state validation, J+3 follow-up activity, invoice propagation, analytic distribution, and open-order closure blockers.
- Docker/Compose runtime, manifests, models, access files, views, migrations, and all existing tests.

## Changes made during this review

- Added the `elmokrif_integration_tests` addon with a cross-module acceptance scenario based on CORE-01, SAL-01, and STK-02.
- Added `scripts/run-system-tests.ps1`, which builds the current image, creates an exact disposable database, installs all four modules, runs their tests, and drops the database in a `finally` block.
- Repaired the sale test fixtures so they satisfy the current chantier master-data and lifecycle rules.
- Added the explicit `sale_stock` dependency required by the sales bridge.
- Strengthened material-request and request-line rules so users must have both an allowed company and access to the related chantier.
- Added a regression proving that a user cannot see another chantier's request in the same company.
- Serialized warehouse-transfer creation with a database row lock, closing the concurrent retry window that could create duplicate transfers.
- Added open material requests to chantier closeout blockers and covered the behavior in the cross-module test.
- Linked generated stock moves to their exact material-request lines, kept equal-product lines separate, and changed delivery status to use fulfilled quantities rather than merely checking whether a transfer ended.
- Added regressions for duplicate-product request lines and short deliveries completed without a backorder.
- Forced both New Chantier entry actions to open in edit mode, supplied the manager-editability default for new records, and added regression tests.

## Guide acceptance mapping

| Guide area | Current status | Evidence |
| --- | --- | --- |
| CORE-01 — one project/account/location relationship | Implemented and passing | Approval initializes the records; repeat initialization reuses them; concurrent initialization is row-locked; lifecycle and company checks are tested. |
| Chantier lifecycle and closeout | Implemented for current modules | Invalid transitions and direct-write bypasses are rejected. Open tasks, site stock, material requests, and sales orders block closing. Reopening requires a reason and records an audit message. |
| Role and multi-company isolation | Implemented for chantier/material scope | Assigned-user, manager, customer, and company rules have restricted-user tests. Material requests now inherit the chantier assignment boundary. |
| SAL-01 — quotation acceptance creates one intended order | Partially implemented and passing for the sales bridge | Orders link to one initialized, in-progress chantier; customer mismatches fail; confirmation is idempotent; invoice lines inherit chantier and analytic allocation. The test does not drive the browser portal or an external email provider. |
| J+3 quotation follow-up | Implemented at model level | One future-dated activity is created, reruns do not duplicate it, and confirmation clears it. Full CRM lead/opportunity reporting is absent. |
| STK-02 — delivery, consumption, return, missing, balance | Implemented for warehouse/site movements | A stock-managed product is delivered to the site, consumed, returned, reported missing, and reconciled to zero site stock. Backorders, request-line-specific receipts, duplicate products, short deliveries, units of measure, and current-cost calculation have regression coverage. |
| Duplicate/retry protection | Implemented for current creation actions | Chantier initialization and transfer creation use database row locks; repeated actions reuse existing records. |
| Purchase requisition and PO approval | Not implemented | No `elmokrif_purchase_chantier` addon, procurement split, purchase-line linkage, or 9,999/10,000/10,001 MAD approval tests. |
| Mandatory receiving quality | Not implemented | No inspection records, Input/Quality/Quarantine gate, quality approver, lot-level decision, or bypass/reversal tests. |
| Accounting and finance operations | Not implemented beyond invoice/analytic propagation | No localization validation, payments/reconciliation, bank matching, cheque workflow, financial exception closeout, or finance acceptance suite. |
| Full CRM workflow | Not implemented | No lead qualification, opportunity stages, targets, site-visit workflow, or CRM reporting acceptance test. |
| HR and confidentiality | Not implemented | No employee/contract/leave/recruitment/appraisal extensions or direct-attachment confidentiality suite. |
| Documents, Discuss/email, and Calendar | Not implemented | No document workspace/version/access bridge, mail-routing acceptance, calendar linkage, or synchronization tests. |
| Management dashboard | Not implemented | No dashboard addon or reconciled KPI tests. |

## System-test scenario added

The new end-to-end Odoo `TransactionCase` performs this sequence:

1. Creates a complete chantier and approves it.
2. Repeats initialization and verifies that the analytic account and site location are reused.
3. Starts the chantier.
4. Creates and sends a quotation, verifies one J+3 follow-up activity, reruns the scheduler, and verifies no duplicate.
5. Confirms the order, verifies the follow-up is removed, creates an invoice, and checks chantier and analytic propagation.
6. Requests and approves ten units of a stock-managed material, creates the warehouse transfer, and validates delivery to the site.
7. Consumes six units and returns two.
8. Confirms closeout fails while two units remain.
9. Reports two units missing, verifies zero site balance and an 80-unit current-cost amount.
10. Confirms a pending material request blocks closeout, cancels it, and closes the chantier.

## Validation result

Run from the repository root:

```powershell
C:\Windows\System32\WindowsPowerShell\v1.0\powershell.exe -NoProfile -ExecutionPolicy Bypass -File .\scripts\run-system-tests.ps1
```

Final Odoo result:

```text
44 post-tests in 15.69s, 14847 queries
0 failed, 0 error(s) of 44 tests
```

Additional static checks passed:

- Python compilation for all custom addons.
- XML parsing for all 17 addon XML files.
- Clean installation of 72 dependency/custom modules in the disposable Odoo database.

## Remaining risks in the implemented scope

1. **Material cost is a current-cost estimate.** It multiplies consumed/missing quantities by the product's current standard price. Changing the standard price changes the displayed cost of past operations. The UI labels this as an estimate, but it is not the guide's historical recognized cost or stock-valuation reconciliation.
2. **The system test is model-level.** It validates real Odoo ORM, security, workflows, stock validation, invoicing, and module installation. It does not automate browser rendering, quotation portal signing, external email delivery, barcode scanning, or third-party synchronization.
3. **The main cross-module path runs as the administrator.** Dedicated tests exercise restricted chantier users and company/assignment isolation, but the entire purchase-to-close scenario has not been replayed through separate real-role accounts as required by the guide's final acceptance approach.
4. **Production still needs user-interface acceptance.** The live upgrade completed and the service restarted cleanly, but the user must hard-refresh the browser and confirm the editable form and normal workflow interactively.

The next implementation milestone should be the guide's purchase-to-consumption pilot: purchase requisition splitting, strict 10,000 MAD approval behavior, purchase-line traceability, and the mandatory quality-release gate. That work is required before the repository can claim the guide's procurement and inventory acceptance gates.
