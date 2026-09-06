from odoo import _, api, fields, models
from odoo.exceptions import ValidationError


class StockLocation(models.Model):
    _inherit = "stock.location"
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
            "stock_location_chantier_uniq",
            "unique(chantier_id)",
            "A chantier can have only one site stock location.",
        ),
    ]

    @api.constrains("chantier_id", "usage", "company_id")
    def _check_chantier_location(self):
        for location in self.filtered("chantier_id"):
            if location.usage != "internal":
                raise ValidationError(_("A chantier location must be internal."))
            if location.company_id != location.chantier_id.company_id:
                raise ValidationError(
                    _("The chantier and its stock location must use the same company.")
                )
