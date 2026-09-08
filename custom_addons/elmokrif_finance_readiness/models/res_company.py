from odoo import api, fields, models


class ResPartner(models.Model):
    _inherit = "res.partner"

    elmokrif_rc_number = fields.Char(
        string="Trade Register (RC)",
        help="Moroccan trade-register reference, kept separately from the 15-digit ICE field.",
    )


class ResCompany(models.Model):
    _inherit = "res.company"

    elmokrif_rc_number = fields.Char(
        related="partner_id.elmokrif_rc_number",
        readonly=False,
        string="Trade Register (RC)",
    )

    @api.model_create_multi
    def create(self, vals_list):
        companies = super().create(vals_list)
        self.env["chantier.finance.readiness"].sudo()._ensure_for_companies(
            companies
        )
        return companies
