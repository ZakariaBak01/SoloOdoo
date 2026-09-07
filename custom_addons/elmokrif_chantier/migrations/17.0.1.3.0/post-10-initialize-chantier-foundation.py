"""Move existing chantiers onto the dedicated analytic plan and repair links."""

from odoo import SUPERUSER_ID, _, api
from odoo.exceptions import UserError


def migrate(cr, version):
    env = api.Environment(cr, SUPERUSER_ID, {})
    project_model = env["project.project"].with_context(active_test=False)
    projects = project_model.search([("is_chantier", "=", True)])
    chantier_plan = env.ref("elmokrif_chantier.analytic_plan_chantier")

    for project in projects:
        analytic_account = project.analytic_account_id
        if analytic_account and analytic_account.plan_id != chantier_plan:
            linked_projects = project_model.search(
                [("analytic_account_id", "=", analytic_account.id)]
            )
            if linked_projects != project:
                raise UserError(
                    _(
                        "Cannot move analytic account %(account)s to the Chantiers "
                        "plan because it is shared by multiple projects.",
                        account=analytic_account.display_name,
                    )
            )
            analytic_account.write({"plan_id": chantier_plan.id})
        if analytic_account and not analytic_account.company_id:
            # Legacy analytic accounts were allowed to have no company.  A
            # chantier-owned account must be scoped to its chantier company.
            analytic_account.write({"company_id": project.company_id.id})
        elif analytic_account and analytic_account.company_id != project.company_id:
            raise UserError(
                _(
                    "Cannot link analytic account %(account)s because it belongs "
                    "to a different company.",
                    account=analytic_account.display_name,
                )
            )
        if analytic_account and not analytic_account.chantier_id:
            analytic_account.with_context(chantier_initialization=True).write(
                {"chantier_id": project.id}
            )
        elif analytic_account and analytic_account.chantier_id != project:
            raise UserError(
                _(
                    "Analytic account %(account)s is linked to a different chantier.",
                    account=analytic_account.display_name,
                )
            )

        site_location = project.site_location_id
        if site_location and not site_location.chantier_id:
            site_location.with_context(chantier_initialization=True).write(
                {"chantier_id": project.id}
            )
        elif site_location and site_location.chantier_id != project:
            raise UserError(
                _(
                    "Site location %(location)s is linked to a different chantier.",
                    location=site_location.display_name,
                )
            )

    projects.filtered(
        lambda project: project.chantier_state != "draft"
        and not project.chantier_initialized
    )._initialize_chantier_resources()
