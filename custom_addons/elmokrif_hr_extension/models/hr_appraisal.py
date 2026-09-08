from odoo import _, api, fields, models
from odoo.exceptions import AccessError, UserError, ValidationError


class HrEmployeeAppraisal(models.Model):
    _name = "elmokrif.hr.appraisal"
    _description = "EL MOKRIF Employee Appraisal"
    _inherit = ["mail.thread", "mail.activity.mixin"]
    _order = "due_date, id desc"
    _check_company_auto = True

    name = fields.Char(required=True, tracking=True)
    employee_id = fields.Many2one(
        "hr.employee",
        required=True,
        tracking=True,
        check_company=True,
    )
    manager_id = fields.Many2one(
        "res.users",
        required=True,
        tracking=True,
        check_company=True,
    )
    company_id = fields.Many2one(
        related="employee_id.company_id",
        store=True,
        readonly=True,
    )
    period_start = fields.Date(required=True, tracking=True)
    period_end = fields.Date(required=True, tracking=True)
    due_date = fields.Date(required=True, tracking=True)
    objectives = fields.Text()
    employee_feedback = fields.Text()
    manager_feedback = fields.Text()
    next_review_date = fields.Date()
    reopen_reason = fields.Text(copy=False)
    completed_at = fields.Datetime(copy=False, readonly=True)
    state = fields.Selection(
        [
            ("draft", "Draft"),
            ("self_assessment", "Self Assessment"),
            ("manager_review", "Manager Review"),
            ("completed", "Completed"),
            ("cancelled", "Cancelled"),
        ],
        default="draft",
        required=True,
        tracking=True,
        copy=False,
    )

    @api.constrains("period_start", "period_end", "due_date")
    def _check_dates(self):
        for appraisal in self:
            if appraisal.period_end < appraisal.period_start:
                raise ValidationError(_("The appraisal period end must follow its start."))

    def _is_hr_manager(self):
        return self.env.su or self.env.user.has_group(
            "elmokrif_hr_extension.group_hr_manager"
        )

    def _is_manager(self, appraisal):
        return self._is_hr_manager() or appraisal.manager_id == self.env.user

    def _is_employee(self, appraisal):
        return appraisal.employee_id.user_id == self.env.user

    def _validate_state_change(self, target):
        transitions = {
            "draft": {"self_assessment", "cancelled"},
            "self_assessment": {"manager_review", "cancelled"},
            "manager_review": {"completed", "cancelled"},
            "completed": {"manager_review"},
            "cancelled": set(),
        }
        for appraisal in self:
            if appraisal.state == target:
                continue
            if target not in transitions.get(appraisal.state, set()):
                raise UserError(_("This appraisal state transition is not allowed."))
            if target == "self_assessment" and not (
                self._is_employee(appraisal) or self._is_manager(appraisal)
            ):
                raise AccessError(_("Only the employee or manager can start the assessment."))
            if target == "manager_review" and not (
                self._is_employee(appraisal) or self._is_manager(appraisal)
            ):
                raise AccessError(
                    _("Only the employee or manager can submit the appraisal for review.")
                )
            if target == "completed" and not self._is_manager(appraisal):
                raise AccessError(_("Only the employee's manager can complete the appraisal."))
            if target == "cancelled" and not self._is_manager(appraisal):
                raise AccessError(_("Only the employee's manager can cancel the appraisal."))
            if target == "manager_review" and not appraisal.employee_feedback:
                raise UserError(_("The employee must submit feedback before manager review."))
            if target == "completed" and not appraisal.manager_feedback:
                raise UserError(_("The manager must submit feedback before completion."))
        return True

    def write(self, vals):
        if "state" in vals:
            raise UserError(
                _("Use the appraisal actions to change its workflow state.")
            )
        for appraisal in self:
            manager_only_fields = {
                "employee_id",
                "manager_id",
                "period_start",
                "period_end",
                "due_date",
                "objectives",
                "next_review_date",
            }
            if manager_only_fields.intersection(vals) and not self._is_manager(appraisal):
                raise AccessError(
                    _("Only the employee's manager can edit appraisal planning details.")
                )
            if "employee_feedback" in vals and not (
                self._is_employee(appraisal) or self._is_manager(appraisal)
            ):
                raise AccessError(
                    _("Only the employee or manager can edit employee feedback.")
                )
            if "manager_feedback" in vals and not self._is_manager(appraisal):
                raise AccessError(
                    _("Only the employee's manager can edit manager feedback.")
                )
            if "reopen_reason" in vals and not self._is_hr_manager():
                raise AccessError(_("Only an HR manager can set a reopening reason."))
            if appraisal.state == "completed" and not (
                set(vals).issubset({"reopen_reason"}) and self._is_hr_manager()
            ):
                raise UserError(
                    _("A completed appraisal is protected from casual edits.")
                )
        return super().write(vals)

    def action_start_self_assessment(self):
        self._validate_state_change("self_assessment")
        super(HrEmployeeAppraisal, self).write({"state": "self_assessment"})

    def action_submit_for_review(self):
        self._validate_state_change("manager_review")
        super(HrEmployeeAppraisal, self).write({"state": "manager_review"})

    def action_complete(self):
        self._validate_state_change("completed")
        super(HrEmployeeAppraisal, self).write(
            {
                "state": "completed",
                "completed_at": fields.Datetime.now(),
            }
        )

    def action_cancel(self):
        self._validate_state_change("cancelled")
        super(HrEmployeeAppraisal, self).write({"state": "cancelled"})

    def action_reopen(self):
        if not self._is_hr_manager():
            raise AccessError(_("Only an HR manager can reopen a completed appraisal."))
        for appraisal in self:
            if appraisal.state != "completed":
                raise UserError(_("Only a completed appraisal can be reopened."))
            if not appraisal.reopen_reason:
                raise ValidationError(_("A reopening reason is required."))
            appraisal.message_post(
                body=_("Appraisal reopened. Reason: %s", appraisal.reopen_reason)
            )
            super(HrEmployeeAppraisal, appraisal).write(
                {
                    "state": "manager_review",
                    "reopen_reason": False,
                    "completed_at": False,
                }
            )
