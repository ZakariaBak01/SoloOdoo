from odoo import Command
from odoo.exceptions import AccessError
from odoo.tests import TransactionCase, tagged


@tagged("post_install", "-at_install")
class TestCalendarBridge(TransactionCase):
    def test_salesperson_creates_site_visit_linked_to_opportunity(self):
        salesperson = self.env["res.users"].with_context(no_reset_password=True).create({
            "name": "Site Visit Salesperson", "login": "site.visit@example.test",
            "company_id": self.env.company.id, "company_ids": [Command.set([self.env.company.id])],
            "groups_id": [Command.set([
                self.env.ref("base.group_user").id,
                self.env.ref("sales_team.group_sale_salesman").id,
            ])],
        })
        customer = self.env["res.partner"].create({"name": "Site Visit Customer"})
        lead = self.env["crm.lead"].with_user(salesperson).create({
            "name": "Site Visit Opportunity", "type": "opportunity",
            "partner_id": customer.id, "user_id": salesperson.id,
            "chantier_site_address": "Construction site address",
        })
        action = lead.action_create_chantier_site_visit_event()
        event = self.env["calendar.event"].browse(action["res_id"])
        self.assertEqual(event.res_id, lead.id)
        self.assertEqual(event.location, "Construction site address")
        self.assertIn(customer, event.partner_ids)

        lead.company_id = False
        shared_action = lead.action_create_chantier_site_visit_event()
        shared_event = self.env["calendar.event"].browse(shared_action["res_id"])
        self.assertEqual(shared_event.company_id, salesperson.company_id)

        other_company = self.env["res.company"].create({"name": "Private Calendar Company"})
        other_event = self.env["calendar.event"].create({
            "name": "Other company appointment", "company_id": other_company.id,
            "start": event.start, "stop": event.stop,
        })
        with self.assertRaises(AccessError):
            other_event.with_user(salesperson).read(["name"])
        self.assertFalse(self.env["calendar.event"].with_user(salesperson).search([
            ("id", "=", other_event.id),
        ]))
