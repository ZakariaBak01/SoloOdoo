# UAT-18 — Work package readiness and field execution

**Users:** U1 manager, U2 responsible site user. **Input:** `CH-UAT-001`, current approved BOQ from UAT-22, package `UAT Foundation Package`, planned quantity 10 m³, dates this month, material budget 1,000 MAD, labour 500 MAD, equipment 200 MAD. **Prerequisite:** approved BOQ; execute BOQ preparation in UAT-22 first.

1. U1: open **EL MOKRIF → Project Control → Work Packages → New**. Enter title, chantier, approved **BOQ**, WBS section and one BOQ line. Set **Manager** U1, **Responsible** U2, planned start/finish, planned quantity `10`, unit `m³`, and budgets 1000/500/200. Click **Save**.
2. Click **Confirm Readiness** with unchecked fields. Record blocker. On **Readiness**, check **Method Statement Ready**, **Drawings Ready**, **Permits Ready**, **Materials Ready** only after attaching the dummy approved method, drawing and permit evidence. Click **Save → Confirm Readiness → Release → Start / Resume**.
3. On **Tasks → Add a line**, enter task `UAT pour slab`, assignee U2, deadline within the package dates, priority. Save and click **Tasks** smart button; verify task/chantiers/package links.
4. U2: open package; set **Installed Quantity** to `11`, save, and record the over-plan validation. Set it to `10`, save. Click **Submit Completed Work**.
5. U1: click **Accept Work**, then **Close**. Record status sequence and actual finish.
6. Create a second work package with first package in **Dependencies**. Try **Release** while predecessor is not Closed (use a third draft predecessor if needed); record denial. Close predecessor, then release the dependent package.

**Pass:** readiness evidence and predecessor closure control release, installed quantity cannot exceed planned scope, and task links stay on the same chantier.
