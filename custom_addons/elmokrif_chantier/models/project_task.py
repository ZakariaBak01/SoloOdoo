from odoo import fields, models

from .project_project import WORK_TYPE_SELECTION


class ProjectTask(models.Model):
    _inherit = "project.task"

    chantier_work_type = fields.Selection(
        WORK_TYPE_SELECTION,
        string="Work Type",
        tracking=True,
    )
