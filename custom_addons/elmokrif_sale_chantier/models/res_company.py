from odoo import _, api, fields, models
from odoo.exceptions import ValidationError


class ResCompany(models.Model):
    _inherit = "res.company"

    sale_chantier_followup_delay_days = fields.Integer(
        string="Chantier Quotation Follow-up Delay",
        default=3,
        help="Number of days after the first quotation send before the salesperson follow-up.",
    )
    sale_chantier_followup_activity_type_id = fields.Many2one(
        "mail.activity.type",
        string="Chantier Quotation Follow-up Activity",
        default=lambda self: self.env.ref(
            "mail.mail_activity_data_todo", raise_if_not_found=False
        ),
    )

    @api.constrains("sale_chantier_followup_delay_days")
    def _check_sale_chantier_followup_delay(self):
        for company in self:
            if company.sale_chantier_followup_delay_days < 0:
                raise ValidationError(
                    _("The chantier quotation follow-up delay cannot be negative.")
                )
