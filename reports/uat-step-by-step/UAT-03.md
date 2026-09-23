# UAT-03 — Opportunity qualification and site visit

**Users:** U7 (sales), U14 (cross-company denial). **Input:** opportunity `UAT Customer A — 30,000 MAD Construction`, customer `UAT Customer A`, expected revenue 30,000 MAD, region `Casablanca-Settat`, expected start 1 Nov 2026, next action `Call customer about site survey`. **Prerequisite:** UAT-01 and U7 listed under chantier Sales Contacts.

1. U7: open **CRM → Pipeline → New**. Enter opportunity title, customer, expected revenue `30000`, salesperson U7, Company A; click **Save**.
2. Open the **Chantier Qualification** tab. Click **Confirm Qualification** with missing fields; record the validation. Enter **Work Type** Construction, **Site Address** `UAT Customer A Site`, **Region**, **Expected Start**, **Contract Value** `30000`, **Decision Maker** a contact at UAT Customer A, **Next Action** as above, and **Chantier** `CH-UAT-002`. Click **Save**, then **Confirm Qualification**. Verify the completion flag.
3. Click **Schedule Site Visit** or **Create Site Visit** in the header (use the visible action). Enter subject `UAT Site Survey`, tomorrow 10:00–11:00, location `UAT Customer A Site`, U7 and the customer as attendees; click **Save** or **Send** as offered by the calendar dialog.
4. Open the created Calendar event; move it to tomorrow 14:00–15:00, click **Save**, and verify the same event was updated. Create a second event named `UAT Cancelled Visit` and cancel/delete it via the Calendar event action; record that the first event remains.
5. From the opportunity's standard **New Quotation** action, create a draft quotation. Check customer, salesperson, company, and selected chantier; select `CH-UAT-002` explicitly if the field is empty. Save and record the quotation number for UAT-04.
6. U14: attempt to open the opportunity and visit using copied URLs; confirm Company A information is denied. U7: try choosing a Company B customer or chantier in the selectors; it should not be selectable.

**Pass:** qualification requires complete business data, the visit and quotation retain the customer/chantier context, and rescheduling does not duplicate events.
