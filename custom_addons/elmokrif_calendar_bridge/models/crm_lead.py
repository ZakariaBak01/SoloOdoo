from datetime import timedelta

from odoo import _, fields, models
from odoo.exceptions import AccessError, UserError


class CrmLead(models.Model):
    _inherit = "crm.lead"

    def action_create_chantier_site_visit_event(self):
        self.ensure_one()
        if not self.env.user.has_group("sales_team.group_sale_salesman"):
            raise AccessError(_("Only a salesperson can create a site visit."))
        if not self.partner_id:
            raise UserError(_("Set a customer before creating a site visit."))
        start = fields.Datetime.now() + timedelta(days=1)
        event = self.env["calendar.event"].create({
            "name": _("Site visit: %s") % self.display_name,
            "start": start,
            "stop": start + timedelta(hours=1),
            "partner_ids": [(4, self.partner_id.id)],
            "location": self.chantier_site_address,
            "user_id": self.user_id.id or self.env.user.id,
            "company_id": (self.company_id or self.env.company).id,
            "chantier_id": self.chantier_id.id,
            "res_model_id": self.env["ir.model"]._get_id("crm.lead"),
            "res_id": self.id,
        })
        return {
            "type": "ir.actions.act_window", "res_model": "calendar.event",
            "view_mode": "form", "res_id": event.id,
        }
