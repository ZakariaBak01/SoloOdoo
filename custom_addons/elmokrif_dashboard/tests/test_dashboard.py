from datetime import date, datetime

from odoo import Command
from odoo.tests import TransactionCase, tagged


@tagged("post_install", "-at_install")
class TestDashboard(TransactionCase):
    def test_dashboard_user_can_read_kpis_without_other_application_roles(self):
        user = self.env["res.users"].with_context(no_reset_password=True).create({
            "name": "Dashboard Only", "login": "dashboard.only@example.test",
            "company_id": self.env.company.id,
            "company_ids": [Command.set([self.env.company.id])],
            "groups_id": [Command.set([
                self.env.ref("base.group_user").id,
                self.env.ref("elmokrif_dashboard.group_elmokrif_dashboard_user").id,
            ])],
        })
        dashboard = self.env["elmokrif.dashboard"].search([
            ("company_id", "=", self.env.company.id),
        ]).with_user(user)
        values = dashboard.read(list(dashboard._kpi_field_names()) + ["access_notice"])[0]
        self.assertEqual(values["monthly_revenue"], 0)
        self.assertIn("Accounting", values["access_notice"])

    def test_sales_include_whole_as_of_day_and_exclude_tomorrow(self):
        dashboard = self.env["elmokrif.dashboard"].search([
            ("company_id", "=", self.env.company.id),
        ])
        dashboard.as_of_date = date(2026, 9, 8)
        customer = self.env["res.partner"].create({"name": "Dashboard Cutoff Customer"})
        today_order, tomorrow_order = self.env["sale.order"].create([
            {"partner_id": customer.id, "date_order": datetime(2026, 9, 8, 15, 30), "state": "sent"},
            {"partner_id": customer.id, "date_order": datetime(2026, 9, 9), "state": "sent"},
        ])
        eligible, _confirmed = dashboard._sale_domains()
        orders = self.env["sale.order"].search(eligible)
        self.assertIn(today_order, orders)
        self.assertNotIn(tomorrow_order, orders)
        dashboard.read(list(dashboard._kpi_field_names()))

    def test_existing_and_new_companies_have_one_dashboard(self):
        dashboard = self.env["elmokrif.dashboard"].search([("company_id", "=", self.env.company.id)])
        self.assertEqual(len(dashboard), 1)
        company = self.env["res.company"].create({"name": "Dashboard New Company"})
        self.assertEqual(
            self.env["elmokrif.dashboard"].search_count([("company_id", "=", company.id)]), 1,
        )
        self.assertEqual(dashboard.action_open_opportunities()["res_model"], "crm.lead")
