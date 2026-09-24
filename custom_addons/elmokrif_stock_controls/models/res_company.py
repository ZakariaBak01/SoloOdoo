from odoo import fields, models


class ResCompany(models.Model):
    _inherit = "res.company"

    chantier_consumption_control_required = fields.Boolean(
        string="Require Approved Chantier Consumption",
        default=False,
        help="When enabled, a chantier consumption picking must come from an approved consumption record.",
    )
