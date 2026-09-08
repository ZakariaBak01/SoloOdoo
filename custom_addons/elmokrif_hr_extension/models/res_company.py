from odoo import _, api, fields, models
from odoo.exceptions import ValidationError


class ResCompany(models.Model):
    _inherit = "res.company"

    hr_contract_expiry_lead_days = fields.Integer(
        string="Contract Expiry Lead Time",
        default=30,
        help="Create the contract expiry activity this many days before the end date.",
    )
    @api.constrains("hr_contract_expiry_lead_days")
    def _check_hr_contract_expiry_lead_days(self):
        for company in self:
            if company.hr_contract_expiry_lead_days < 0:
                raise ValidationError(
                    _("The contract expiry lead time cannot be negative.")
                )
