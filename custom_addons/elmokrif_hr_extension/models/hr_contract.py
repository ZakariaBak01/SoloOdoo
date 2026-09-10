from datetime import timedelta

from odoo import _, api, fields, models
from odoo.exceptions import UserError

_HR_CONTRACT_WORKFLOW_TOKEN = object()


class HrContract(models.Model):
    _inherit = "hr.contract"

    hr_expiry_activity_id = fields.Many2one(
        "mail.activity",
        string="Expiry Activity",
        copy=False,
        readonly=True,
        ondelete="set null",
    )
    hr_expiry_activity_created = fields.Boolean(
        string="Expiry Activity Created",
        copy=False,
        readonly=True,
    )

    def _in_expiry_workflow(self):
        return self.env.context.get("_hr_contract_workflow_token") is _HR_CONTRACT_WORKFLOW_TOKEN

    @api.model_create_multi
    def create(self, vals_list):
        protected = {"hr_expiry_activity_id", "hr_expiry_activity_created"}
        default_protected = {
            key[8:] for key in self.env.context if key.startswith("default_")
        }
        if protected.intersection(default_protected) or any(
            protected.intersection(values) for values in vals_list
        ):
            raise UserError(_("Expiry activity metadata is managed by the HR workflow."))
        return super().create(vals_list)

    def _expiry_owner(self):
        self.ensure_one()
        manager = self.employee_id.parent_id.user_id
        if manager:
            return manager
        managers = self.env.ref(
            "elmokrif_hr_extension.group_hr_manager"
        ).sudo().users.filtered(
            lambda user: user.active and self.company_id in user.company_ids
        )
        return managers[:1] or self.env.user

    @api.model
    def _cron_create_contract_expiry_activities(self):
        today = fields.Date.context_today(self)
        company_ids = self.env["res.company"].sudo().search([]).ids
        contracts = self.sudo().with_context(allowed_company_ids=company_ids).search(
            [
                ("date_end", "!=", False),
                ("date_end", ">=", today),
                ("hr_expiry_activity_created", "=", False),
                ("state", "not in", ("close", "cancel")),
            ]
        )
        activity_type = self.env.ref(
            "elmokrif_hr_extension.mail_activity_type_contract_expiry",
            raise_if_not_found=False,
        )
        if not activity_type:
            return 0

        created = 0
        for contract in contracts:
            self.env.cr.execute(
                "SELECT id FROM hr_contract WHERE id = %s FOR UPDATE",
                [contract.id],
            )
            contract.invalidate_recordset(
                ["state", "date_end", "hr_expiry_activity_created", "hr_expiry_activity_id"]
            )
            if (
                contract.hr_expiry_activity_created
                or contract.state in ("close", "cancel")
            ):
                continue
            lead_days = contract.company_id.hr_contract_expiry_lead_days
            if contract.date_end > today + timedelta(days=lead_days):
                continue
            owner = contract._expiry_owner()
            activity = contract.activity_schedule(
                activity_type_id=activity_type.id,
                date_deadline=contract.date_end,
                user_id=owner.id,
                summary=_("Contract expiry review"),
                note=_(
                    "Review contract %(contract)s for %(employee)s before %(date)s.",
                    contract=contract.name,
                    employee=contract.employee_id.name,
                    date=contract.date_end,
                ),
            )
            contract.with_context(_hr_contract_workflow_token=_HR_CONTRACT_WORKFLOW_TOKEN).write(
                {
                    "hr_expiry_activity_id": activity.id,
                    "hr_expiry_activity_created": True,
                }
            )
            created += 1
        return created

    def write(self, vals):
        if not self._in_expiry_workflow() and {
            "hr_expiry_activity_id",
            "hr_expiry_activity_created",
        }.intersection(vals):
            raise UserError(
                _("Expiry activity metadata is managed by the HR workflow.")
            )
        old_activities = {
            contract.id: contract.hr_expiry_activity_id
            for contract in self
            if "date_end" in vals and contract.date_end != vals["date_end"]
        }
        result = super().write(vals)
        if "date_end" in vals:
            for contract in self.filtered(lambda item: item.id in old_activities):
                old_activity = old_activities[contract.id]
                if old_activity:
                    old_activity.unlink()
                contract.with_context(_hr_contract_workflow_token=_HR_CONTRACT_WORKFLOW_TOKEN).write(
                    {
                        "hr_expiry_activity_id": False,
                        "hr_expiry_activity_created": False,
                    }
                )
        return result

    def action_reset_expiry_activity(self):
        if not (
            self.env.su
            or self.env.user.has_group("elmokrif_hr_extension.group_hr_manager")
        ):
            raise UserError(_("Only an HR manager can reset an expiry activity."))
        for contract in self:
            if contract.hr_expiry_activity_id:
                contract.hr_expiry_activity_id.unlink()
            contract.with_context(_hr_contract_workflow_token=_HR_CONTRACT_WORKFLOW_TOKEN).write(
                {
                    "hr_expiry_activity_id": False,
                    "hr_expiry_activity_created": False,
                }
            )
        return True
