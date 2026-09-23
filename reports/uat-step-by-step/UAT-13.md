# UAT-13 — Controlled document approval and revision

**Users:** U9 document user; U10 document manager; U14 isolation. **Input:** `UAT Construction Contract`, category Contract, `CH-UAT-001`, owner U9, `uat-contract-v1.pdf` then `uat-contract-v2.pdf`. **Prerequisite:** UAT-01.

1. U9: open **Documents → Controlled Documents → New**. Enter **Name**, **Category** Contract, Company A, **Chantier** `CH-UAT-001`, **Owner** U9, issue date today, expiry one year later, **Attachment** v1 PDF. Click **Save → Submit for Review**.
2. U10: open the in-review document. Click **Reject** and provide reason `Missing signature` if prompted; verify **Rejected** and reviewer evidence in chatter. U9 replaces the draft attachment with corrected v1, clicks **Save → Submit for Review**.
3. U10: click **Approve**. Record revision number and attachment link. Attempt to replace, relink, delete, or make the approved attachment public; these should be denied.
4. U10: click **Create Revision**. On the new draft attach v2 and set issue/expiry dates; click **Save**. Verify v1 stays current **Approved** until v2 is approved. Submit v2; U10 clicks **Approve**. Verify v1 **Superseded** and v2 current **Approved**.
5. Set a test document's expiry near/past due date in a draft/revision. UAT administrator runs the document expiry scheduled action twice from **Settings → Technical → Automation → Scheduled Actions**. U10 counts related activities: only one per required reminder.
6. Search **Controlled Documents** by chantier, category, owner, state and expiry. U14 pastes direct URLs to the Company A document and attachment; record denial and absence of preview.

**Pass:** decisions and revisions preserve audit history, only one approved current revision exists, expiry activities do not duplicate, and Company B cannot read document or file.
