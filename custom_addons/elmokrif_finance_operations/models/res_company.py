from odoo import fields, models


class ResCompany(models.Model):
    _inherit = "res.company"

    elmokrif_reminder_template_7_id = fields.Many2one(
        "mail.template", string="7-day Overdue Reminder Template",
        domain="[('model', '=', 'account.move')]",
    )
    elmokrif_reminder_template_15_id = fields.Many2one(
        "mail.template", string="15-day Overdue Reminder Template",
        domain="[('model', '=', 'account.move')]",
    )
    elmokrif_reminder_template_30_id = fields.Many2one(
        "mail.template", string="30-day Overdue Reminder Template",
        domain="[('model', '=', 'account.move')]",
    )
