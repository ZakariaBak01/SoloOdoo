# UAT-14 — Employee leave, appraisal, contract, and applicant

**Users:** U11 employee; U12 HR manager; UAT administrator runs expiry job. **Input:** U11 leave next month for 2 days, appraisal `UAT U11 Q4 Review`, contract expiring within configured lead time. **Prerequisite:** U11 employee linked to U12 manager in Company A.

1. U11: open **Time Off → My Time Off → New**. Select a configured leave type, U11, two dates next month, note `UAT personal leave`; click **Save → Submit**. Try changing **Employee** to another person and record denial.
2. U12: open **Time Off → Management → Time Off** (menu wording may vary), locate U11's request, click standard **Approve** or **Refuse**. For a refusal, enter **Refusal Reason**; verify state and timestamp. Repeat with a new leave request and approve it; test cancellation on a separate request.
3. U12: open **Employees → Employee Appraisals → New**. Enter `UAT U11 Q4 Review`, **Employee** U11, **Manager** U12, period 1 Oct–31 Dec 2026, due 15 Jan 2027, objectives `Complete site reporting training`; click **Save → Start Self-Assessment**.
4. U11: open own appraisal, enter **Employee Feedback** `Training complete`, click **Save → Submit for Review**. U12: enter **Manager Feedback** `Meets objectives`, click **Save → Complete**. Try editing completed feedback; record denial.
5. U12: enter **Reopen Reason** `Correct objective evidence`, save, click **Reopen**; verify chatter and editable state. Close it again after correction.
6. U12: open **Employees → Contracts**, create/open a UAT contract for U11 with end date inside the configured expiry lead days. UAT administrator runs the contract-expiry Scheduled Action twice. Verify one activity, not two.
7. U12: open **Recruitment → Applications** and convert a dummy applicant `UAT Candidate A` to an employee using the visible **Create Employee** action; verify the employee/company link.
8. U11 and an unrelated user paste direct URLs for another employee's leave, appraisal, contract, applicant, and attachment; record access denial without preview.

**Pass:** employee self-service stays private; manager decisions retain reasons and audit data; completed appraisals are protected; contract expiry activity is unique.
