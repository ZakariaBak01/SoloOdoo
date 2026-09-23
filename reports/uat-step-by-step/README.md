# EL MOKRIF: role-based UI acceptance tests

Use a disposable Odoo 17 UAT database with the custom modules installed. Run UAT-00 through UAT-15, then the BOQ preparation in UAT-22 before UAT-18/20/21; run UAT-16/17 after the linked workflows. Each UAT is a separate test record and evidence sheet, although later UATs reuse earlier records. The previous overview is [the UAT playbook](../2026-09-09-ui-ux-uat-workflow.md). These files are the operator instructions.

## Before the first test

1. UAT administrator: sign in to the UAT database; confirm Company A is **EL MOKRIF COMPANY SARL**, currency **MAD**, and Company B is **UAT ISOLATION COMPANY B**. Never use production for invalid-input, return, void, or closeout cases.
2. UAT administrator: in **Settings → Users & Companies → Users**, verify the named accounts and allowed companies below. Use the account's actual password from the UAT setup; do not record passwords in evidence.
3. U8: verify one sales tax, one purchase tax, Sales/Purchase/Bank journals, Chart of Accounts, the **Sales Region** analytic plan, and its **Casablanca Sales** analytic account. Record the actual tax rate and approval threshold; examples below are tax-exclusive unless stated.
4. U1: verify `UAT Customer A`, its delivery address `UAT Customer A Site`, `UAT Supplier A`, `UAT Supplier B`, `Construction Service` (service), `Cement Bag` (50 kg bag), `Steel Bar` (kg), `Paint Bucket` (unit), a volume unit such as m³, warehouse `WH-A`, and a second-company customer. Create missing records through their normal Contacts/Inventory menus before testing.
5. U1: reserve the names `CH-UAT-001` and `CH-UAT-002` for UAT-01; if either already exists in this database, record it and reuse it instead of making a duplicate. Both must use `UAT Customer A`, valid site addresses, `WH-A`, U1 as manager, and U2/U3/U4/U6 as assigned team where their work requires it. Add U7 under **Sales Contacts** on both chantiers during UAT-01. The provisioning script only auto-links U7 to `CH-UAT-001` when that record already exists.
6. UAT administrator: have two small dummy files ready (`uat-contract-v1.pdf`, `uat-contract-v2.pdf`), a cement data sheet, a test vendor quotation, a method statement, drawing, permit, measurement sheet, and a controlled sample bank CSV. Use non-sensitive data.
7. Copy the [result sheet](RESULT-TEMPLATE.md) for every UAT. Record database name, date/time, company, logged-in account, browser, record reference, screenshots, actual result, and defect ID. Mark a step **Blocked** when its prerequisite or button is unavailable; record the exact error. Do not silently complete a business-user step as Administrator.

## User and access map

| User | Sign-in name | Business role | Main tasks |
| --- | --- | --- | --- |
| U1 | `uat.u1.manager` | Chantier Manager | Chantier approval, initialization, estimates, consumption approval, project-control decisions, closeout |
| U2 | `uat.u2.chantier` | Chantier User / BOQ Estimator | Site tasks, estimates, requests, daily reports, consumption, BOQ preparation, field control |
| U3 | `uat.u3.buyer` | Buyer | RFQs, supplier choice, tender buying, returns |
| U4 | `uat.u4.purchase.approver` | Purchase Approver / BOQ Reviewer | Purchase approval, BOQ review, tender evaluation and award approval |
| U5 | `uat.u5.storekeeper` | Storekeeper | Receipts, transfers, stock and supplier return validation |
| U6 | `uat.u6.quality` | Quality Inspector | Quality acceptance/rejection; separate from U5 |
| U7 | `uat.u7.sales` | Salesperson | CRM, quotations, sales orders, customer PDF and follow-up |
| U8 | `uat.u8.accountant` | Accountant | Analytic setup, readiness, invoices, bank, collection, cheques, certificate invoicing |
| U9 | `uat.u9.documents` | Document User | Draft and submit controlled documents |
| U10 | `uat.u10.document.manager` | Document Manager | Reject, approve, revise and archive documents |
| U11 | `uat.u11.employee` | Employee | Own leave and appraisal |
| U12 | `uat.u12.hr.manager` | HR Manager | Leave, appraisal, contracts, applicant conversion |
| U13 | `uat.u13.dashboard` | Dashboard User | KPI checks and permitted company switch |
| U14 | `uat.u14.companyb` | Company B User | Company isolation and direct-link denial |

U1's manager group implies several specialist permissions. Preserve separation of people: U2 prepares BOQs, U4 reviews, U1 approves; U3 buys, U4 evaluates/approves; U5 receives, U6 inspects. The named provisioning script supplies these groups, but verify the effective rights in UAT-00. For a certificate needing separate submitter and verifier, use U8 and U4 if both have **Progress Certifier** access, then U1 approves; if a role lacks it, have the UAT administrator grant the documented group before execution and record that setup change.

## Test files

| Phase | Test | Primary users |
| --- | --- | --- |
| Access | [UAT-00](UAT-00.md) | U1–U14 |
| Chantier | [UAT-01](UAT-01.md) | U1, U2, U14 |
| Estimation | [UAT-02](UAT-02.md) | U1, U2 |
| CRM/calendar | [UAT-03](UAT-03.md) | U7, U14 |
| Sales | [UAT-04](UAT-04.md) | U7, U8, U1 |
| Material request | [UAT-05](UAT-05.md) | U2, U1, U3, U5 |
| Purchasing | [UAT-06](UAT-06.md) | U3, U4 |
| Quality | [UAT-07](UAT-07.md) | U5, U6, U3 |
| Consumption | [UAT-08](UAT-08.md) | U2, U1, U5 |
| Daily cost | [UAT-09](UAT-09.md) | U2, U1, U8 |
| Finance | [UAT-10](UAT-10.md) | U8, U7 |
| Bank | [UAT-11](UAT-11.md) | U8 |
| Collections | [UAT-12](UAT-12.md) | U8 |
| Documents | [UAT-13](UAT-13.md) | U9, U10, U14 |
| HR | [UAT-14](UAT-14.md) | U11, U12 |
| Dashboard | [UAT-15](UAT-15.md) | U13, U8, U14 |
| Closeout (after linked workflows) | [UAT-16](UAT-16.md) | U1, U2, U5 |
| Security (last) | [UAT-17](UAT-17.md) | U1–U14 |
| Work packages | [UAT-18](UAT-18.md) | U1, U2 |
| Issues/RFI/submittals | [UAT-19](UAT-19.md) | U2, U1 |
| Changes/variations | [UAT-20](UAT-20.md) | U2, U1, U4 |
| Certification | [UAT-21](UAT-21.md) | U8, U4, U1 |
| BOQ/tender award (BOQ prep before UAT-18) | [UAT-22](UAT-22.md) | U2, U4, U1, U3 |

Use the exact labels shown in the installed English UI. Standard Odoo buttons sometimes change with state (for example **Create Invoice** becomes **Create Invoices**); write the visible label in the evidence if it differs. Any manually run Scheduled Action requires a UAT administrator and is explicitly identified in the relevant test.
