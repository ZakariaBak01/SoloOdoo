# UAT-19 — Site issue, RFI, and material submittal

**Users:** U2 raises and responds; U1 verifies and decides. **Input:** `CH-UAT-001`, issue `UAT Drawing Conflict`, RFI `UAT RFI Slab Detail`, submittal `UAT Cement Data Sheet`; response/review due in two days. **Prerequisite:** UAT-01 and an approved BOQ line from UAT-22.

1. U2: open **EL MOKRIF → Project Control → Site Issues → New**. Enter title, chantier, category, **Severity** High, **Responsible** U2, due date, location `North slab`, description `Drawing dimension conflicts with site measurement`; attach a dummy photo, click **Save → Assign**.
2. Enter **Resolution** `Measurement and drawing checked`, click **Save → Resolve**. Try **Close** before verification and record denial. U1: open issue and click **Verify**. U2: click **Close**; record status and chatter.
3. On a second open issue, click **Create RFI**. Enter question `Which slab dimension controls?`, responsible U1, response due date and BOQ line; click **Save → Submit**. U1: click **Start Review**, enter answer `Use revised drawing UAT-DWG-02`, cost impact `1000` MAD, schedule impact `2` days, click **Save → Record Answer → Close**. Record timestamps and reciprocal issue link.
4. On the answered RFI click **Create Change Event**; verify source RFI/issue links and continue in UAT-20.
5. U2: open **Project Control → Submittals → New**. Enter title, chantier, type Material, specification `UAT-SPEC-CEM-01`, BOQ line, submitted-by supplier/contact, reviewer U1 and review due date. Click **Save → Submit** without file; record validation.
6. Attach `uat-cement-datasheet-v1.pdf`, click **Save → Submit**. U1: click **Start Review**, enter **Review Comment** `Use approved grade`, click **Save → Approve as Noted**. Click **New Revision**; attach v2 and verify v1 remains immutable/superseded.
7. Set another RFI/submittal due date in the past and refresh the chantier health assessment through its scheduled action or normal refresh. Check At Risk/Off Track signal and reason.

**Pass:** issue verification is separate from resolution, RFI and change preserve origin, submittal approval requires evidence/comment, and overdue records affect health.
