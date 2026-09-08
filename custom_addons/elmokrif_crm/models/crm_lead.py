from odoo import _, api, fields, models
from odoo.exceptions import AccessError, UserError, ValidationError


class CrmLead(models.Model):
    _inherit = "crm.lead"

    chantier_work_type = fields.Selection(
        [
            ("construction", "Construction"),
            ("carpentry", "Carpentry"),
            ("finishing", "Finishing"),
        ],
        string="Work Type",
        tracking=True,
    )
    chantier_site_address = fields.Char(string="Site Address", tracking=True)
    chantier_region = fields.Char(string="Region", tracking=True)
    chantier_contract_value = fields.Monetary(
        string="Approximate Contract Value",
        currency_field="company_currency",
        tracking=True,
    )
    chantier_expected_start = fields.Date(string="Expected Start", tracking=True)
    chantier_decision_maker_id = fields.Many2one(
        "res.partner", string="Decision Maker", tracking=True
    )
    chantier_next_action = fields.Char(string="Next Action", tracking=True)
    chantier_id = fields.Many2one(
        "project.project",
        string="Chantier",
        check_company=True,
        ondelete="restrict",
        domain="[('is_chantier', '=', True), ('company_id', '=', company_id)]",
        tracking=True,
    )
    chantier_qualification_complete = fields.Boolean(
        compute="_compute_chantier_qualification_complete",
        string="Qualification Complete",
    )

    @api.depends(
        "partner_id",
        "chantier_work_type",
        "chantier_site_address",
        "chantier_region",
        "chantier_contract_value",
        "chantier_expected_start",
        "chantier_decision_maker_id",
        "chantier_next_action",
    )
    def _compute_chantier_qualification_complete(self):
        for lead in self:
            lead.chantier_qualification_complete = bool(
                lead.partner_id
                and lead.chantier_work_type
                and lead.chantier_site_address
                and lead.chantier_region
                and lead.chantier_contract_value > 0
                and lead.chantier_expected_start
                and lead.chantier_decision_maker_id
                and lead.chantier_next_action
            )

    @api.constrains("chantier_id", "company_id")
    def _check_chantier_company(self):
        for lead in self.filtered("chantier_id"):
            if lead.chantier_id.company_id != lead.company_id:
                raise ValidationError(_("The chantier must belong to the opportunity company."))

    def action_chantier_mark_qualified(self):
        for lead in self:
            if not lead.chantier_qualification_complete:
                raise UserError(_(
                    "Complete the customer, work type, site address, region, expected value, "
                    "expected start, decision maker and next action before qualifying this opportunity."
                ))
            lead.message_post(body=_("Chantier qualification completed."))
        return True

    def action_chantier_schedule_site_visit(self):
        if not self.env.user.has_group("sales_team.group_sale_salesman"):
            raise AccessError(_("Only a salesperson can schedule a site visit."))
        activity_type = self.env.ref("mail.mail_activity_data_meeting", raise_if_not_found=False)
        if not activity_type:
            activity_type = self.env.ref("mail.mail_activity_data_todo")
        for lead in self:
            existing = self.env["mail.activity"].search([
                ("res_model", "=", "crm.lead"),
                ("res_id", "=", lead.id),
                ("activity_type_id", "=", activity_type.id),
                ("date_done", "=", False),
                ("summary", "=", "Site visit"),
            ], limit=1)
            if not existing:
                lead.activity_schedule(
                    activity_type_id=activity_type.id,
                    user_id=lead.user_id.id or self.env.user.id,
                    summary=_("Site visit"),
                    note=_("Qualify the site and record findings on this opportunity."),
                )
        return True

    def _prepare_opportunity_quotation_context(self):
        context = super()._prepare_opportunity_quotation_context()
        if self.chantier_id:
            context["default_chantier_id"] = self.chantier_id.id
        return context
