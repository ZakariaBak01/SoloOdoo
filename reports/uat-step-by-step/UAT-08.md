# UAT-08 — Site transfer, consumption, and unused return

**Users:** U5 transfers, U2 consumes, U1 approves. **Input:** `CH-UAT-001`, 10 cement bags transferred to site, 6 consumed, 4 unused. **Prerequisite:** approved request and central stock from UAT-05.

1. U5: open **EL MOKRIF → Material Requests → [approved request] → Site Transfers**. Open the cement transfer, enter **Done** quantity `10` or the available amount, click **Validate**. In `CH-UAT-001`, verify its site location and on-hand quantity increased by the validated amount.
2. U1: if chantier is In Progress, click **Put on Hold** for the negative test. U2: open **EL MOKRIF → Approved Consumptions → New**, choose `CH-UAT-001`, today, work type Construction, add Cement Bag quantity `1`, click **Save → Submit**. Record the state blocker. U1: click **Start** to resume.
3. U2: create a fresh consumption; select `CH-UAT-001`, **Operation Date** today, work type Construction. Under **Lines → Add a line**, select Cement Bag and enter more than site on-hand; click **Save → Submit** and record rejection. Correct line quantity to `6`, then **Save → Submit**.
4. U2: attempt **Approve and Consume** on own submitted record; record the denial. U1: open it and click **Approve and Consume**. Record linked picking and state. Refresh and try again if the button is still shown; verify exactly one completed stock effect for 6 bags.
5. U5: open the original source-linked site transfer in **Inventory → Operations → Transfers** and use the standard **Return** action for the unused `4` bags, selecting the correct origin and destination. Validate the return. If the transfer has no supported Return action, mark this subcase blocked and record the screen; do not create an unlinked inventory adjustment.
6. Compare site on-hand: opening site stock + 10 transfer − 6 consumption − 4 return = opening site stock. Check consumption and return valuation/source references separately.

**Pass:** consumption requires In Progress and approval by another user; one approval causes one stock effect; unused return is tied to its source transfer.
