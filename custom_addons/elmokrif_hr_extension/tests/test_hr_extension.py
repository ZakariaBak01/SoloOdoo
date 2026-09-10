import base64
from datetime import date, timedelta

from odoo.exceptions import AccessError, UserError, ValidationError
from odoo.tests import TransactionCase, tagged


@tagged("post_install", "-at_install")
class TestHrExtension(TransactionCase):
    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.company = cls.env.company
        cls.manager_user = cls.env.user
        cls.manager_employee = cls.env["hr.employee"].create(
            {
                "name": "HR Test Manager",
                "user_id": cls.manager_user.id,
                "company_id": cls.company.id,
            }
        )
        cls.employee_user = cls.env["res.users"].with_context(
            no_reset_password=True
        ).create(
            {
                "name": "HR Test Employee User",
                "login": "hr_test_employee",
                "email": "hr-test-employee@example.test",
                "groups_id": [
                    (
                        6,
                        0,
                        [
                            cls.env.ref("base.group_user").id,
                            cls.env.ref(
                                "elmokrif_hr_extension.group_hr_employee"
                            ).id,
                        ],
                    )
                ],
            }
        )
        cls.hr_manager_user = cls.env["res.users"].with_context(
            no_reset_password=True
        ).create(
            {
                "name": "HR Test Manager User",
                "login": "hr_test_manager",
                "email": "hr-test-manager@example.test",
                "groups_id": [
                    (
                        6,
                        0,
                        [
                            cls.env.ref("base.group_user").id,
                            cls.env.ref(
                                "elmokrif_hr_extension.group_hr_manager"
                            ).id,
                        ],
                    )
                ],
            }
        )
        cls.hr_officer_user = cls.env["res.users"].with_context(
            no_reset_password=True
        ).create(
            {
                "name": "HR Test Officer User",
                "login": "hr_test_officer",
                "email": "hr-test-officer@example.test",
                "groups_id": [(6, 0, [
                    cls.env.ref("base.group_user").id,
                    cls.env.ref("elmokrif_hr_extension.group_hr_officer").id,
                ])],
            }
        )
        cls.untrusted_hr_user = cls.env["res.users"].with_context(
            no_reset_password=True
        ).create(
            {
                "name": "Standard HR User",
                "login": "hr_test_standard",
                "email": "hr-test-standard@example.test",
                "groups_id": [(6, 0, [
                    cls.env.ref("base.group_user").id,
                    cls.env.ref("hr.group_hr_user").id,
                ])],
            }
        )
        cls.employee = cls.env["hr.employee"].create(
            {
                "name": "HR Test Employee",
                "user_id": cls.employee_user.id,
                "parent_id": cls.manager_employee.id,
                "company_id": cls.company.id,
            }
        )

    def _create_appraisal(self):
        return self.env["elmokrif.hr.appraisal"].create(
            {
                "name": "2026 Annual Review",
                "employee_id": self.employee.id,
                "manager_id": self.manager_user.id,
                "period_start": date(2026, 1, 1),
                "period_end": date(2026, 12, 31),
                "due_date": date(2026, 12, 15),
            }
        )

    def test_appraisal_workflow_protects_completion_and_requires_reopen_reason(self):
        appraisal = self._create_appraisal()
        with self.assertRaises(UserError):
            appraisal.write({"state": "completed"})
        with self.assertRaises(UserError):
            appraisal.with_context(hr_appraisal_completion=True).write(
                {"state": "completed"}
            )

        appraisal.with_user(self.employee_user).action_start_self_assessment()
        appraisal.with_user(self.employee_user).write(
            {"employee_feedback": "Self-assessment completed."}
        )
        appraisal.action_submit_for_review()
        appraisal.write({"manager_feedback": "Manager review completed."})
        appraisal.action_complete()

        with self.assertRaises(UserError):
            appraisal.write({"manager_feedback": "Unauthorized edit"})
        with self.assertRaises(ValidationError):
            appraisal.action_reopen()

        appraisal.write({"reopen_reason": "Corrective review required."})
        appraisal.action_reopen()
        self.assertEqual(appraisal.state, "manager_review")

    def test_appraisal_identity_and_reopen_state_are_protected(self):
        appraisal = self._create_appraisal()
        with self.assertRaises(AccessError):
            appraisal.with_user(self.employee_user).write(
                {"manager_id": self.employee_user.id}
            )

        appraisal.write({"reopen_reason": "Not applicable in draft."})
        with self.assertRaises(UserError):
            appraisal.action_reopen()

    def test_appraisal_creation_and_completion_evidence_cannot_be_forged(self):
        values = {
            "name": "Protected review", "employee_id": self.employee.id,
            "manager_id": self.manager_user.id, "period_start": date(2027, 1, 1),
            "period_end": date(2027, 12, 31), "due_date": date(2027, 12, 15),
        }
        with self.assertRaises(AccessError):
            self.env["elmokrif.hr.appraisal"].with_user(self.employee_user).create(values)
        with self.assertRaises(AccessError):
            self.env["elmokrif.hr.appraisal"].create(dict(values, state="completed"))

        appraisal = self.env["elmokrif.hr.appraisal"].with_user(self.hr_officer_user).create(values)
        self.assertEqual(appraisal.state, "draft")
        with self.assertRaises(AccessError):
            appraisal.with_user(self.employee_user).write(
                {"completed_at": "2027-12-15 12:00:00"}
            )

    def test_hr_attachment_download_is_limited_to_custom_hr_officers(self):
        attachment = self.env["ir.attachment"].create(
            {
                "name": "confidential-contract.pdf",
                "datas": base64.b64encode(b"confidential contract"),
                "mimetype": "application/pdf", "res_model": "hr.employee",
                "res_id": self.employee.id,
            }
        )
        with self.assertRaises(AccessError):
            attachment.with_user(self.untrusted_hr_user).check("read")
        attachment.with_user(self.hr_officer_user).check("read")
        with self.assertRaises(AccessError):
            self.env["ir.attachment"].create(
                {
                    "name": "public-contract.pdf", "datas": base64.b64encode(b"confidential contract"),
                    "mimetype": "application/pdf", "res_model": "hr.employee",
                    "res_id": self.employee.id, "public": True,
                }
            )

    def test_employee_cannot_see_another_employee_appraisal(self):
        other_employee = self.env["hr.employee"].create({"name": "Other Employee"})
        other_appraisal = self.env["elmokrif.hr.appraisal"].create(
            {
                "name": "Other Review",
                "employee_id": other_employee.id,
                "manager_id": self.manager_user.id,
                "period_start": date(2026, 1, 1),
                "period_end": date(2026, 12, 31),
                "due_date": date(2026, 12, 15),
            }
        )

        visible = self.env["elmokrif.hr.appraisal"].with_user(
            self.employee_user
        ).search([("id", "=", other_appraisal.id)])
        self.assertFalse(visible)
        with self.assertRaises(AccessError):
            other_appraisal.with_user(self.employee_user).write(
                {"employee_feedback": "Forbidden"}
            )

    def test_employee_can_only_create_own_leave(self):
        leave_type = self.env["hr.leave.type"].create(
            {
                "name": "HR Test Leave",
                "requires_allocation": "no",
                "leave_validation_type": "hr",
                "company_id": self.company.id,
            }
        )
        own_leave = self.env["hr.leave"].with_user(self.employee_user).create(
            {
                "name": "Own leave",
                "employee_id": self.employee.id,
                "holiday_status_id": leave_type.id,
                "request_date_from": date.today(),
                "request_date_to": date.today(),
            }
        )
        self.assertEqual(own_leave.employee_id, self.employee)
        with self.assertRaises(AccessError):
            own_leave.with_user(self.employee_user).write(
                {"employee_id": self.manager_employee.id}
            )
        own_leave.with_user(self.hr_manager_user).action_validate()
        with self.assertRaises(UserError):
            own_leave.with_user(self.employee_user).with_context(
                hr_leave_correction=True
            ).write({"request_date_from": date.today() + timedelta(days=1)})

        with self.assertRaises(AccessError):
            self.env["hr.leave"].with_user(self.employee_user).create(
                {
                    "name": "Other leave",
                    "employee_id": self.manager_employee.id,
                    "holiday_status_id": leave_type.id,
                    "request_date_from": date.today(),
                    "request_date_to": date.today(),
                }
            )

    def test_leave_two_step_approval_refusal_and_cancellation(self):
        leave_type = self.env["hr.leave.type"].create(
            {"name": "Two step HR Test Leave", "requires_allocation": "no",
             "leave_validation_type": "both", "company_id": self.company.id}
        )
        leave = self.env["hr.leave"].with_user(self.employee_user).create(
            {"name": "Approved leave", "employee_id": self.employee.id,
             "holiday_status_id": leave_type.id, "request_date_from": date.today(),
             "request_date_to": date.today()}
        )
        self.assertEqual(leave.state, "confirm")
        leave.with_user(self.hr_manager_user).action_approve()
        self.assertEqual(leave.state, "validate1")
        leave.with_user(self.hr_manager_user).action_validate()
        self.assertEqual(leave.state, "validate")
        self.assertTrue(leave.hr_approval_completed_at)
        self.assertEqual(self.env["hr.leave"]._elmokrif_count_approved_absences(self.company, date.today()), 1)
        with self.assertRaises(AccessError):
            leave.with_user(self.employee_user)._action_user_cancel("Employee cannot self-cancel approval.")
        self.env["hr.holidays.cancel.leave"].with_user(self.hr_manager_user).create(
            {"leave_id": leave.id, "reason": "Leave cancelled by HR."}
        ).action_cancel_leave()
        self.assertFalse(leave.active)
        self.assertEqual(self.env["hr.leave"]._elmokrif_count_approved_absences(self.company, date.today()), 0)

        refused = self.env["hr.leave"].with_user(self.employee_user).create(
            {"name": "Refused leave", "employee_id": self.employee.id,
             "holiday_status_id": leave_type.id, "request_date_from": date.today() + timedelta(days=2),
             "request_date_to": date.today() + timedelta(days=2)}
        )
        self.assertEqual(refused.state, "confirm")
        with self.assertRaises(UserError):
            refused.with_user(self.hr_manager_user).action_refuse()
        refused.with_user(self.hr_manager_user).write(
            {"hr_refusal_reason": "Operational coverage is required."}
        )
        refused.with_user(self.hr_manager_user).action_refuse()
        self.assertEqual(refused.state, "refuse")

    def test_recruitment_creates_an_employee_and_appraisal_stays_confidential(self):
        job = self.env["hr.job"].create({"name": "HR Test Recruiter Job"})
        applicant = self.env["hr.applicant"].create(
            {"name": "Recruitment Candidate", "partner_name": "Recruitment Candidate",
             "email_from": "candidate@example.test", "job_id": job.id}
        )
        employee = self.env["hr.employee"].browse(applicant.create_employee_from_applicant()["res_id"])
        self.assertTrue(employee.exists())
        self.assertEqual(employee.applicant_id, applicant)
        candidate_appraisal = self.env["elmokrif.hr.appraisal"].create(
            {"name": "Candidate probation review", "employee_id": employee.id,
             "manager_id": self.manager_user.id, "period_start": date(2027, 1, 1),
             "period_end": date(2027, 12, 31), "due_date": date(2027, 12, 15)}
        )
        self.assertFalse(self.env["elmokrif.hr.appraisal"].with_user(self.employee_user).search(
            [("id", "=", candidate_appraisal.id)]
        ))

    def test_contract_expiry_activity_is_idempotent_and_configurable(self):
        self.company.hr_contract_expiry_lead_days = 30
        contract = self.env["hr.contract"].create(
            {
                "name": "HR Test Contract",
                "employee_id": self.employee.id,
                "date_start": date.today(),
                "date_end": date.today() + timedelta(days=10),
                "wage": 1000,
                "company_id": self.company.id,
            }
        )

        created = self.env["hr.contract"]._cron_create_contract_expiry_activities()
        self.assertEqual(created, 1)
        activity = contract.hr_expiry_activity_id
        self.assertTrue(activity)

        created = self.env["hr.contract"]._cron_create_contract_expiry_activities()
        self.assertEqual(created, 0)
        self.assertEqual(contract.hr_expiry_activity_id, activity)

        contract.action_reset_expiry_activity()
        self.assertFalse(contract.hr_expiry_activity_id)
        with self.assertRaises(UserError):
            contract.write({"hr_expiry_activity_created": True})
