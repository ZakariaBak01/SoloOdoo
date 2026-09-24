# UAT-01 — Chantier master data and lifecycle

**Users:** U2 (denied creation), U1 (manager), U14 (isolation). **Inputs:** `CH-UAT-001` and `CH-UAT-002`, `UAT Customer A`, delivery address `UAT Customer A Site`, warehouse `WH-A`, region `Casablanca-Settat`, work type `Construction`, dates 1 Oct–31 Dec 2026. **Prerequisite:** UAT-00.

1. U2: open **EL MOKRIF → All Chantiers**. Verify **New Chantier** is absent; try creating from any visible generic **New** action and record the denial.
2. U1: search **All Chantiers** for `CH-UAT-001`. If it already exists, open and complete its setup; otherwise open **EL MOKRIF → New Chantier**. In the title enter `CH-UAT-001`; select Company A. On **Chantier**, select **Customer** `UAT Customer A`, **Chantier Manager** U1, **Chantier Team** U2/U3/U4/U6, **Sales Contacts** U7, and **Site Address** `UAT Customer A Site`.
3. Enter **Planned Dates** 1 Oct–31 Dec 2026, **Work Type** Construction, **Chantier Region** `Casablanca-Settat`, **Warehouse** `WH-A`; leave the site address empty once and click **Approve and Initialize**. Record the required-data error, then restore the address.
4. Click **Save**, then **Approve and Initialize**. Verify status **Approved**, initialized message, an analytic account, a site stock location, and an initialization note in chatter. Record the generated **Chantier Reference**; do not assume the typed title is the generated reference.
5. Click **Initialize Chantier** only if the button is shown as a recovery action. Reopen the record; confirm no second analytic account or site location.
6. Click **Start**. Verify **In Progress**. Click **Put on Hold**; verify **On Hold**. Click **Start** again; verify **In Progress**.
7. Open **Tasks**, **Estimates**, **Sales**, and **Material Requests** smart buttons where visible. Each list must belong to this chantier and its count must match the visible records.
8. Repeat steps 2–4 for `CH-UAT-002`, reusing it if already present; use the same customer/company/warehouse, U1 as manager, U7 under **Sales Contacts**. Click **Start** so sales confirmation can use it. Search **All Chantiers** for each name/reference and record exactly one match.
9. U14: paste the direct URL for `CH-UAT-001`. Record access denied with no Company A data.

**Pass:** only U1 creates/approves, both chantiers initialize once, and Company B cannot read either. Keep both active for later UATs.
