# UAT-09 — Daily reports and live estimate cost

**Users:** U2 enters site facts, U1 reviews baseline, U8 checks financial totals. **Input:** `CH-UAT-001`; daily report for today: 12 work units, 8 labour hours, 2 equipment hours, 400 MAD equipment cost, 50 MAD other cost, weather `Clear`, blocker `Delivery expected tomorrow`. **Prerequisite:** approved estimate UAT-02 and site activity UAT-08.

1. U2: open **EL MOKRIF → Daily Site Reports → New**. Select `CH-UAT-001`, today, a valid cost code, weather, work quantity `12`, work unit from the available options, labour hours `8`, equipment hours `2`, equipment cost `400`, other cost `50`; enter blocker text and attach a dummy photo. Click **Save**.
2. Create a second draft report with work quantity `-1` or labour hours `-1`; click **Save** and record the validation. Correct it or discard that draft.
3. U2: open `CH-UAT-001` tasks, complete one task and leave one open. U1: open the **Estimates** smart button, then the current approved estimate's **Live Cost Control** tab. Check completed/total task count and calculated progress. Manual progress must only be used when no tasks exist.
4. Compare estimate **Actual Labour Cost**, **Actual Machinery Cost**, **Actual Other Cost**, **Actual Material Cost**, **Actual Cost**, and **Cost Variance** with the saved report and UAT-08 consumption. Record the visible totals and any missing source link.
5. U8: open the relevant customer invoice, supplier bill and credit note when created in UAT-10. Compare invoiced revenue, collected cash, commitments and actual cost on chantier/project-control views. Verify a credit note reduces net revenue and an internal transfer does not appear as consumption cost.

**Pass:** site facts are entered once, live progress follows tasks, and cost/revenue/commitment measures remain distinct with working drilldowns. Steps that depend on UAT-10 can be completed after that test.
