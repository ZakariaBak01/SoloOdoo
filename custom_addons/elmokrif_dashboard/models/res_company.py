from odoo import api, models


class ResCompany(models.Model):
    _inherit = "res.company"

    @api.model_create_multi
    def create(self, values_list):
        companies = super().create(values_list)
        Dashboard = self.env["elmokrif.dashboard"].sudo()
        for company in companies:
            if not Dashboard.search_count([("company_id", "=", company.id)]):
                Dashboard.create({"company_id": company.id})
        return companies
