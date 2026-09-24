# UAT-04 — Ordinary sales, chantier sales, and follow-up

**Users:** U7 sells; U8 checks the second analytic dimension and later invoices; U1 verifies chantier count. **Input:** `UAT Customer A`, `CH-UAT-002`, `Construction Service` at 30,000 MAD, one `Cement Bag` at 85 MAD, `Casablanca Sales` analytic account. **Prerequisite:** UAT-01 and U7 in `CH-UAT-002` **Sales Contacts**.

1. U7: open **Sales → Orders → Quotations → New**. Select `UAT Customer A`, leave **Chantier** blank, add **Construction Service** quantity `1`, click **Save**, then **Confirm**. Verify the resulting sales order has no chantier and no chantier was created.
2. U7: click **New** again. Select `UAT Customer A`, then choose existing **Chantier** `CH-UAT-002` beside the customer. Add **Construction Service** quantity `1`, unit price `30000`; add **Cement Bag** quantity `1`, price `85`. Verify each line's **Chantier** column shows `CH-UAT-002`; click **Save**.
3. U8: ensure **Sales Region → Casablanca Sales** exists under analytic accounts. U7: edit the service line's **Analytic Distribution** and set `Casablanca Sales` to 100%. Save, reopen the line, and check both the chantier analytic account and Casablanca Sales remain at 100% in their separate plans.
4. U7: click **Send by Email**. Inspect the generated quotation PDF and customer preview/portal link in the composer; confirm customer, lines, totals, and chantier reference. Send only to the UAT customer address. Record the quotation number and first sent time.
5. On the sent quotation, inspect **Activities**: one **Chantier quotation follow-up** with deadline three days after first send (or the configured company delay). Click **Send by Email** again and send to the UAT address; refresh **Activities**. There must still be one follow-up. This module schedules on first send; there is no separate J+3 cron in this module.
6. U7: click **Confirm**. Verify **Sales Order**, follow-up activity removed, and the two lines still linked to `CH-UAT-002`.
7. U1: open **EL MOKRIF → All Chantiers → CH-UAT-002**, record **Sales** count and the first chantier order number before the next step.
8. U7: open **Sales → Orders → Quotations → New**. Select the same customer and existing `CH-UAT-002`; add **Construction Service** quantity `1`, price `1000`; **Save → Confirm**. Record this second chantier order number.
9. U1: search **All Chantiers** for `CH-UAT-002` and open its **Sales** smart button. Verify there is exactly one chantier record, both chantier orders appear in its sales list, and the Sales count increased by one. If confirmation reports initialization or commitment-state problems, return to UAT-01 and record this as blocked.

**Pass:** ordinary order stays ordinary; both chantier orders use the same existing chantier; two analytic plans survive; only one follow-up activity is created and it closes on confirmation.
