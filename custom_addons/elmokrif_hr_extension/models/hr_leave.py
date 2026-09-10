from odoo import _, api, fields, models
from odoo.exceptions import AccessError, UserError

_HR_LEAVE_WORKFLOW_TOKEN = object()
_HR_LEAVE_CANCELLATION_TOKEN = object()


class HrLeave(models.Model):
    _inherit = "hr.leave"

    hr_approval_completed_at = fields.Datetime(
        string="HR Approval Completed At",
        copy=False,
        readonly=True,
    )
    hr_refusal_reason = fields.Text(
        string="Refusal Reason",
        copy=False,
        readonly=True,
    )

    def _is_hr_manager(self):
        return self.env.su or self.env.user.has_group(
            "elmokrif_hr_extension.group_hr_manager"
        )

    def _in_workflow(self):
        return self.env.context.get("_hr_leave_workflow_token") is _HR_LEAVE_WORKFLOW_TOKEN

    def _can_manage_leave(self, leave):
        employee = leave.employee_id
        return self._is_hr_manager() or (
            employee.parent_id and employee.parent_id.user_id == self.env.user
        )

    @api.model_create_multi
    def create(self, vals_list):
        evidence_fields = {"hr_approval_completed_at", "hr_refusal_reason"}
        default_evidence = {
            key[8:] for key in self.env.context if key.startswith("default_")
        }
        if evidence_fields.intersection(default_evidence) or any(
            evidence_fields.intersection(values) for values in vals_list
        ):
            raise AccessError(_("Leave approval evidence is managed by the HR workflow."))
        records = super().create(vals_list)
        for leave in records:
            if not self._can_manage_leave(leave) and (
                leave.employee_id.user_id != self.env.user
            ):
                raise AccessError(_("Employees can only request leave for themselves."))
        return records

    def write(self, vals):
        protected_fields = {
            "employee_id",
            "holiday_status_id",
            "request_date_from",
            "request_date_to",
            "date_from",
            "date_to",
            "number_of_days",
            "number_of_hours_display",
            "attachment_ids",
        }
        for leave in self:
            if "employee_id" in vals and leave.employee_id.id != vals["employee_id"]:
                raise AccessError(
                    _("The employee on a leave request cannot be changed.")
                )
            if "hr_approval_completed_at" in vals and not self._in_workflow():
                raise AccessError(
                    _("Leave approval evidence is managed by the HR workflow.")
                )
            if "hr_refusal_reason" in vals and not (
                self._is_hr_manager() and leave.state not in ("validate", "refuse", "cancel")
            ):
                raise AccessError(_("Only an HR manager can record a refusal reason before refusal."))
            if leave.state == "validate" and protected_fields.intersection(vals):
                raise UserError(
                    _("An approved leave cannot be edited; cancel it through the approval flow.")
                )
            if leave.state == "validate" and vals.get("state") not in (None, "cancel"):
                raise UserError(
                    _("An approved leave can only be cancelled through the approval flow.")
                )
        result = super().write(vals)
        return result

    def action_validate(self):
        result = super().action_validate()
        for leave in self:
            leave.sudo().with_context(
                _hr_leave_workflow_token=_HR_LEAVE_WORKFLOW_TOKEN
            ).write({"hr_approval_completed_at": fields.Datetime.now()})
        return result

    def action_refuse(self):
        if any(not (leave.hr_refusal_reason or "").strip() for leave in self):
            raise UserError(_("Record a refusal reason before refusing a leave request."))
        result = super().action_refuse()
        return result

    def action_cancel(self):
        if any(leave.state == "validate" for leave in self) and not self._is_hr_manager():
            raise AccessError(_("Only an HR manager can cancel an approved leave."))
        return super().action_cancel()

    def _action_user_cancel(self, reason):
        if self.env.context.get("_hr_leave_cancellation_token") is _HR_LEAVE_CANCELLATION_TOKEN:
            return super()._action_user_cancel(reason)
        if any(leave.state == "validate" for leave in self) and not self._is_hr_manager():
            raise AccessError(_("Only an HR manager can cancel an approved leave."))
        approved = self.filtered(lambda leave: leave.state == "validate")
        if approved:
            requester = approved.employee_id.user_id
            if not requester:
                raise UserError(_("An approved leave needs an employee user before it can be cancelled."))
            return approved.with_user(requester).with_context(
                _hr_leave_cancellation_token=_HR_LEAVE_CANCELLATION_TOKEN
            )._action_user_cancel(reason)
        return super()._action_user_cancel(reason)

    @api.model
    def _elmokrif_count_approved_absences(self, company, as_of_date):
        """Return only a company-scoped aggregate for the management dashboard.

        A dashboard user must not receive the underlying leave records or any
        medical/supporting-document data merely to display today's absence KPI.
        """
        dashboard_group = self.env.ref(
            "elmokrif_dashboard.group_elmokrif_dashboard_user",
            raise_if_not_found=False,
        )
        if not (self._is_hr_manager() or dashboard_group and self.env.user in dashboard_group.users):
            raise AccessError(_("You are not allowed to read absence aggregates."))
        if company not in self.env.companies:
            raise AccessError(_("Select an allowed company."))
        leaves = self.sudo().search([
            ("company_id", "=", company.id),
            ("state", "=", "validate"),
            ("request_date_from", "<=", as_of_date),
            ("request_date_to", ">=", as_of_date),
        ])
        return len(set(leaves.mapped("employee_id").ids))
