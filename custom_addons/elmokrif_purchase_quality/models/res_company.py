from odoo import fields, models


class ResCompany(models.Model):
    _inherit = "res.company"

    chantier_purchase_approval_threshold = fields.Monetary(
        string="Chantier Purchase Approval Threshold",
        currency_field="currency_id",
        default=10000.0,
        help="Untaxed company-currency amount at or above which a distinct approver is required.",
    )
    chantier_purchase_two_person = fields.Boolean(
        string="Require Distinct Purchase Approver",
        default=True,
    )
    chantier_quality_required = fields.Boolean(
        string="Require Quality Inspection for Chantier Purchases",
        default=True,
    )

