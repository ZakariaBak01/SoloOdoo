from odoo import api, fields, models
from odoo.exceptions import ValidationError

from .utils import validate_chantier_link


class ResPartner(models.Model):
    _inherit = "res.partner"

    default_chantier_id = fields.Many2one(
        "project.project",
        string="Default Chantier",
        check_company=True,
        domain="[('is_chantier', '=', True), '|', ('company_id', '=', False), ('company_id', '=', company_id)]",
        help="Used as the default chantier on new quotations for this customer.",
    )

    @api.constrains("default_chantier_id", "company_id")
    def _check_default_chantier(self):
        for partner in self:
            if partner.default_chantier_id:
                validate_chantier_link(
                    partner.default_chantier_id,
                    partner.default_chantier_id.company_id,
                    partner,
                )
                if partner.company_id and partner.default_chantier_id.company_id != partner.company_id:
                    raise ValidationError(
                        "The default chantier must belong to the partner company."
                    )
