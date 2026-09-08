from datetime import timedelta

from odoo import _, api, fields, models
from odoo.exceptions import UserError


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

    @api.model
    def _cron_create_contract_expiry_activities(self):
        today = fields.Date.context_today(self)
        contracts = self.search(
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
            owner = (
                contract.employee_id.parent_id.user_id
                or contract.employee_id.user_id
                or self.env.user
            )
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
            super(HrContract, contract).write(
                {
                    "hr_expiry_activity_id": activity.id,
                    "hr_expiry_activity_created": True,
                }
            )
            created += 1
        return created

    def write(self, vals):
        if {
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
                super(HrContract, contract).write(
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
            super(HrContract, contract).write(
                {
                    "hr_expiry_activity_id": False,
                    "hr_expiry_activity_created": False,
                }
            )
        return True
