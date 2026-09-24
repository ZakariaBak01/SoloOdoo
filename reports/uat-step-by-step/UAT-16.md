# UAT-16 — Complete, close, reopen, and archive a chantier

**Users:** U2 completes work; U1 closes/reopens/archives. **Input:** a disposable chantier separate from active `CH-UAT-001` and `CH-UAT-002`, named `UAT Closeout Site`; one open task and one bag of site stock as blockers. **Prerequisite:** UAT-01 and any linked documents/financial tests completed.

1. U1: open **EL MOKRIF → New Chantier** and create `UAT Closeout Site` with the same required master fields as UAT-01. Click **Save → Approve and Initialize → Start**. Create one open task on it; transfer one test bag to its site location.
2. U2: open the chantier and click **Complete**. U1: click **Close**. Record the error listing open task and remaining site stock. Check whether open requests, POs, inspections, documents, orders, variations and certificates also appear; record each unresolved source and any omitted blocker as a defect.
3. U2: complete the open task. U5: use the source-linked transfer **Return** action for the remaining site bag, validate, and verify zero site stock. Resolve other blockers using each source record's own workflow.
4. U1: click **Close** again. Verify **Closed** and timestamp/chatter evidence. Try creating a new material request, sales order, or consumption for the closed chantier and record each denial.
5. U1: click **Edit**, enter **Reopen Reason** `UAT correction after closeout`, click **Save → Reopen**. Verify status returns to **Approved**, an audit note names the reason, and the chantier is active. Click **Start** if further activity is needed.
6. U2: click **Complete** after cleanup; U1 clicks **Close**, then **Archive**. In **All Chantiers**, search active records and verify the archived chantier disappears. Use the **Archived** filter to confirm its history, tasks, documents and accounting links remain accessible to authorized users.

**Pass:** closure blocks unresolved work, reopening requires a reason, and archive preserves history. The current UI reports blockers as an error list; it does not open a separate closeout wizard. Record missing links or omitted blockers as defects.
