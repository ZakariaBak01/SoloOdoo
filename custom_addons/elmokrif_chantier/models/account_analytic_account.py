from odoo import _, api, fields, models
from odoo.exceptions import UserError, ValidationError


class AccountAnalyticAccount(models.Model):
    _inherit = "account.analytic.account"
    _check_company_auto = True

    chantier_id = fields.Many2one(
        "project.project",
        string="Chantier",
        copy=False,
        ondelete="restrict",
        check_company=True,
        domain="[('is_chantier', '=', True), ('company_id', '=', company_id)]",
        index=True,
    )

    _sql_constraints = [
        (
            "analytic_account_chantier_uniq",
            "unique(chantier_id)",
            "A chantier can have only one analytic account.",
        ),
    ]

    @api.model_create_multi
    def create(self, vals_list):
        if not self.env.context.get("chantier_initialization") and any(
            values.get("chantier_id") for values in vals_list
        ):
            raise UserError(
                _("Use Initialize Chantier to create and link an analytic account.")
            )
        return super().create(vals_list)

    def write(self, vals):
        if (
            "chantier_id" in vals
            and not self.env.context.get("chantier_initialization")
            and any(account.chantier_id.id != vals["chantier_id"] for account in self)
        ):
            raise UserError(
                _("Use Initialize Chantier to change the chantier analytic link.")
            )
        return super().write(vals)

    def unlink(self):
        if any(account.chantier_id for account in self):
            raise UserError(
                _("An analytic account linked to a chantier cannot be deleted.")
            )
        return super().unlink()

    @api.constrains("chantier_id", "company_id", "plan_id")
    def _check_chantier_account(self):
        chantier_plan = self.env.ref(
            "elmokrif_chantier.analytic_plan_chantier",
            raise_if_not_found=False,
        )
        for account in self.filtered("chantier_id"):
            if account.company_id != account.chantier_id.company_id:
                raise ValidationError(
                    _("The chantier and analytic account must use the same company.")
                )
            if chantier_plan and account.plan_id != chantier_plan:
                raise ValidationError(
                    _("A chantier analytic account must use the Chantiers plan.")
                )
