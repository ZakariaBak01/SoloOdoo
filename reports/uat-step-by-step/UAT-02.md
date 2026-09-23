# UAT-02 — Estimate, approval, revision, and variance

**Users:** U2 prepares, U1 approves. **Input:** `CH-UAT-001`; estimate `UAT Slab A`; length 10 m, width 5 m, depth 0.2 m, wastage 5%, cement 300 kg/m³, 50 kg/bag, cement cost 80 MAD/bag, sand 150 MAD/m³, gravel 200 MAD/m³, labour 30 MAD/hour, machinery 500 MAD/day; phase split 60/30/10. **Prerequisite:** UAT-01.

1. U2: open **EL MOKRIF → All Chantiers → CH-UAT-001 → Estimates → New** (or **EL MOKRIF → Construction Estimates → New**). Enter **Name** `UAT Slab A`, **Chantier** `CH-UAT-001`, and the values above in **Site and Dimensions**, **Materials**, **Labour and Machinery**, and **Cost Summary**. Use the configured tax.
2. Set **Length** to `0` and click **Save**; capture the validation. Restore `10`. Set a negative cost, save, capture the validation, and restore it. Set **Foundation/Superstructure/Finishing** to `60/30/20`; save and capture the phase-total error; restore `60/30/10`.
3. Click **Save** and compare **Net Volume**, **Adjusted Volume**, material, labour, and total cost to a calculator. Record displayed values and currency.
4. Click **Submit**. U2 opens the submitted estimate and attempts **Approve**; the action must be unavailable or denied.
5. U1: open the same estimate and click **Approve**. Verify **Approved**, approver/time, and baseline on the chantier. Attempt to edit the approved dimensions and record the readonly/denial.
6. U2: click **Create Revision**. In the draft revision change **Wastage %** from `5` to `7`, save, and check that the first approved estimate remains the active baseline. Click **Submit**.
7. U1: click **Approve** on the revision. Verify it is the approved baseline and the predecessor is **Superseded**.
8. U2: on **Live Cost Control**, enter actual labour hours `10`, machinery cost `600`, other cost `100` where allowed; record the variance. U1: if the overrun exposes **Approve Variance**, click it and capture required reason/evidence and audit details. If no overrun is shown, record this subcase as not triggered rather than claiming an approval.

**Pass:** invalid inputs are blocked, U2 cannot approve, only one current approved baseline exists, and the prior baseline remains available as history.
