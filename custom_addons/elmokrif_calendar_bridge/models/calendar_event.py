from odoo import _, api, fields, models
from odoo.exceptions import ValidationError


class CalendarEvent(models.Model):
    _inherit = "calendar.event"

    chantier_id = fields.Many2one(
        "project.project", string="Chantier", check_company=True,
        domain="[('is_chantier', '=', True), ('company_id', '=', company_id)]",
    )
    elmokrif_document_id = fields.Many2one(
        "elmokrif.document", string="Controlled Document", check_company=True,
        domain="[('company_id', '=', company_id)]",
    )
    company_id = fields.Many2one(
        "res.company", default=lambda self: self.env.company, required=True,
    )

    @api.constrains("chantier_id", "elmokrif_document_id", "company_id")
    def _check_elmokrif_company_links(self):
        for event in self:
            if event.chantier_id and event.chantier_id.company_id != event.company_id:
                raise ValidationError(_("The chantier must use the event company."))
            if event.elmokrif_document_id and event.elmokrif_document_id.company_id != event.company_id:
                raise ValidationError(_("The controlled document must use the event company."))
