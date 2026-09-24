# UAT-00 — Named users, menus, and company isolation

**Users:** U1–U14; UAT administrator sets up accounts only. **Input:** Company A and Company B from [setup](README.md). **Evidence:** one screenshot per role, list of visible apps, and denied direct-link result.

1. UAT administrator: open **Settings → Users & Companies → Users**. Open each `uat.uN...` user and verify **Access Rights** and **Allowed Companies** match the [role map](README.md). Save any missing role assignment before the business test; record the change.
2. U1: sign out of Administrator, sign in as `uat.u1.manager`, switch to Company A, open **EL MOKRIF → All Chantiers**. Verify **New Chantier**, **Construction Estimates**, **Material Requests**, **Project Control**, and **Tendering & BOQ** as permitted. Record the landing menu.
3. U2: sign in, open **EL MOKRIF → All Chantiers**. Verify **New Chantier** is absent. If `CH-UAT-001` already exists, search it and check assigned site access; otherwise repeat that record check immediately after UAT-01. Repeat for U3/U4/U6; each sees their own work menus and assigned chantier when it exists.
4. U5: sign in and open **Inventory → Operations → Receipts**. Verify receipt/transfer actions and absence of **Approve and Release** on an inspection.
5. U7: sign in; open **CRM → Pipeline** and **Sales → Orders → Quotations**. Verify U7 cannot open operational chantier menus. After UAT-01, search `CH-UAT-002` in a new quotation's **Chantier** field and confirm U7 can select it.
6. U8: sign in; open **Accounting → Configuration → Chantier Finance Readiness**, **Accounting → Bank Imports**, and **Accounting → Customers → Invoices**.
7. U9/U10: each sign in and open **Documents → Controlled Documents**. U9 should submit; U10 should see review actions on an in-review document.
8. U11/U12: each sign in and open the HR/Time Off and Appraisal menus available to their role. U11 must see own records only; U12 has management actions.
9. U13: sign in, open **Management Dashboard**, choose Company A, then Company B in the company selector; record permitted values and drilldowns.
10. U14: sign in and inspect company selector; Company A must be unavailable. After the records exist, paste the browser URL of `CH-UAT-001`, a Company A document, and Company A dashboard record. Record access denial without disclosed names, amounts, or attachments.
11. Repeat U2's main chantier form at a phone-width browser window. Confirm core fields and **Submit** buttons remain reachable.

**Pass:** all 14 named roles can log in and reach only intended menus and records; U14 cannot see Company A. Any unexpected visible menu, missing menu, or leaked preview is a defect.
