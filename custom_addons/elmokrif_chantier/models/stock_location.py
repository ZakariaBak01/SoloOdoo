from odoo import _, api, fields, models
from odoo.exceptions import UserError, ValidationError

from .workflow import CHANTIER_INITIALIZATION_TOKEN


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

    @api.model_create_multi
    def create(self, vals_list):
        if self.env.context.get("_chantier_initialization_token") is not CHANTIER_INITIALIZATION_TOKEN and (
            self.env.context.get("default_chantier_id")
            or any(values.get("chantier_id") for values in vals_list)
        ):
            raise UserError(
                _("Use Initialize Chantier to create and link a site location.")
            )
        return super().create(vals_list)

    def write(self, vals):
        if (
            "chantier_id" in vals
            and self.env.context.get("_chantier_initialization_token") is not CHANTIER_INITIALIZATION_TOKEN
            and any(location.chantier_id.id != vals["chantier_id"] for location in self)
        ):
            raise UserError(
                _("Use Initialize Chantier to change a site-location link.")
            )
        return super().write(vals)

    @api.constrains("chantier_id", "usage", "company_id")
    def _check_chantier_location(self):
        for location in self.filtered("chantier_id"):
            if location.usage != "internal":
                raise ValidationError(_("A chantier location must be internal."))
            if location.company_id != location.chantier_id.company_id:
                raise ValidationError(
                    _("The chantier and its stock location must use the same company.")
                )
