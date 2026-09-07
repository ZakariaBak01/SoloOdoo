from odoo import fields, models


class MailActivity(models.Model):
    _inherit = "mail.activity"

    is_chantier_followup = fields.Boolean(
        string="Chantier Quotation Follow-up",
        copy=False,
        index=True,
    )
