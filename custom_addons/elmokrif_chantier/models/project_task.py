from odoo import _, api, fields, models
from odoo.exceptions import UserError, ValidationError

from .project_project import WORK_TYPE_SELECTION


class ProjectTask(models.Model):
    _inherit = "project.task"

    is_chantier_project = fields.Boolean(
        related="project_id.is_chantier",
        string="Chantier Task",
    )
    chantier_work_type = fields.Selection(
        WORK_TYPE_SELECTION,
        string="Work Type",
        tracking=True,
    )
    chantier_bundle = fields.Char(string="Work Bundle", tracking=True)

    @api.model_create_multi
    def create(self, vals_list):
        tasks = super().create(vals_list)
        tasks.mapped("project_id").filtered("is_chantier")._refresh_chantier_health()
        return tasks

    def write(self, vals):
        projects = self.mapped("project_id")
        result = super().write(vals)
        (projects | self.mapped("project_id")).filtered("is_chantier")._refresh_chantier_health()
        return result

    def unlink(self):
        projects = self.mapped("project_id").filtered("is_chantier")
        result = super().unlink()
        projects._refresh_chantier_health()
        return result

    def _get_task_board_chantier(self):
        project_id = self.env.context.get("default_project_id")
        project = self.env["project.project"].browse(project_id).exists()
        if not project or not project.is_chantier:
            raise UserError(_("These actions are available from a chantier Tasks page."))
        return project

    def action_new_detailed_chantier_task(self):
        project = self._get_task_board_chantier()
        project._ensure_chantier_user()
        return {
            "type": "ir.actions.act_window",
            "name": _("New Detailed Task"),
            "res_model": "project.task",
            "view_mode": "form",
            "views": [(self.env.ref("project.view_task_form2").id, "form")],
            "target": "current",
            "context": {
                **self.env.context,
                "default_project_id": project.id,
            },
        }

    def action_refresh_task_board_chantier_health(self):
        project = self._get_task_board_chantier()
        project._ensure_chantier_user()
        project._refresh_chantier_health()
        return {"type": "ir.actions.client", "tag": "reload"}

    @api.onchange("project_id")
    def _onchange_chantier_project(self):
        for task in self.filtered(lambda item: not item.is_chantier_project):
            task.chantier_work_type = False

    @api.constrains("project_id", "chantier_work_type")
    def _check_chantier_work_type(self):
        if any(
            task.chantier_work_type and not task.is_chantier_project for task in self
        ):
            raise ValidationError(
                _("A chantier work type can only be set on a chantier task.")
            )
