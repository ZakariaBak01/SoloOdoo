from odoo import fields, models


class ProjectProject(models.Model):
    _inherit = "project.project"

    estimation_ids = fields.One2many("chantier.estimation", "chantier_id", string="Estimates")
    estimation_count = fields.Integer(compute="_compute_estimation_count")

    def _compute_estimation_count(self):
        for project in self:
            project.estimation_count = len(project.estimation_ids)

    def action_view_estimates(self):
        self.ensure_one()
        return {"type": "ir.actions.act_window", "name": "Construction Estimates", "res_model": "chantier.estimation", "view_mode": "tree,form", "domain": [("chantier_id", "=", self.id)], "context": {"default_chantier_id": self.id}}
