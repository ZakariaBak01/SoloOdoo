from odoo import _, api, fields, models
from odoo.exceptions import ValidationError

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
