from odoo import _, api, fields, models
from odoo.exceptions import AccessError, UserError


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

    def _can_manage_leave(self, leave):
        employee = leave.employee_id
        return self._is_hr_manager() or (
            employee.parent_id and employee.parent_id.user_id == self.env.user
        )

    @api.model_create_multi
    def create(self, vals_list):
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
            if {
                "hr_approval_completed_at",
                "hr_refusal_reason",
            }.intersection(vals) and not self._is_hr_manager():
                raise AccessError(
                    _("Only an HR manager can change HR approval metadata.")
                )
            if leave.state == "validate" and protected_fields.intersection(vals):
                if not self._is_hr_manager():
                    raise UserError(
                        _("An approved leave cannot be edited; cancel it through the approval flow.")
                    )
            if leave.state == "validate" and vals.get("state") not in (None, "cancel"):
                if not self._is_hr_manager():
                    raise UserError(
                        _("An approved leave can only be cancelled or changed by HR.")
                    )
        result = super().write(vals)
        return result

    def action_validate(self):
        result = super().action_validate()
        for leave in self:
            leave.sudo().write({"hr_approval_completed_at": fields.Datetime.now()})
        return result

    def action_refuse(self):
        result = super().action_refuse()
        return result

    def action_cancel(self):
        return super().action_cancel()
