# UAT-17 — Direct URL, list, and cross-company security regression

**Users:** U14 plus the least-privilege user for each record; U1 witnesses. **Input:** exact record URLs created by UAT-01 through UAT-22. **Prerequisite:** create at least one record per tested model in Company A and one harmless Company B record.

1. U1: copy direct URLs for a Company A chantier, estimate, material request, inspection, consumption, document/attachment, BOQ, tender, issue, RFI, variation, certificate, invoice, leave and appraisal. Store references in the evidence sheet, not credentials.
2. U14: sign in with Company B only. Paste each Company A URL, then refresh. Record denied view and check that title, amount, chatter, file thumbnail and linked-record previews remain hidden.
3. U14: use visible list search, **Group By**, Favorites, and Export where allowed; search `CH-UAT-001` and `UAT Customer A`. Record any Company A row or aggregate value.
4. U2: try opening a Company A chantier to which U2 is not assigned. U7: try opening a procurement approval and U8's bank import. U5: try approving a quality inspection. U9: try approving a controlled document. U11: try viewing another employee's contract. Record each server-side denial.
5. In a disposable role session with Developer Mode, try editing readonly status/approver fields on a draft or completed test record and using any available import feature to set company, state or source link. Record whether the server rejects it; do not alter production data.
6. U1: verify intended manager access to Company A records while Company B remains inaccessible. Reopen one denied URL as U1 to distinguish a broken URL from proper access control.

**Pass:** ACLs and record rules protect read/write/create/delete, child lines, attachments and summaries, including direct URLs and list aggregates. Do not infer security from a hidden button alone.
