from datetime import date

from odoo import Command
from odoo.exceptions import AccessError, UserError
from odoo.tests import TransactionCase, tagged


@tagged("post_install", "-at_install")
class TestApprovedConsumption(TransactionCase):
    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.company = cls.env.company
        cls.warehouse = cls.env["stock.warehouse"].search([("company_id", "=", cls.company.id)], limit=1)
        cls.requester = cls._user("Consumption Requester", "consumption.requester@example.test", "elmokrif_stock_controls.group_chantier_consumption_user")
        cls.approver = cls._user("Consumption Approver", "consumption.approver@example.test", "elmokrif_stock_controls.group_chantier_consumption_approver")
        partner = cls.env["res.partner"].create({
            "name": "Consumption Customer",
            "customer_rank": 1,
        })
        site = cls.env["res.partner"].create({
            "name": "Consumption Site Address",
            "type": "other",
        })
        cls.chantier = cls.env["project.project"].with_context(default_is_chantier=True).create({
            "name": "Consumption Site", "is_chantier": True, "company_id": cls.company.id,
            "warehouse_id": cls.warehouse.id, "partner_id": partner.id,
            "site_partner_id": site.id, "user_id": cls.approver.id,
            "chantier_member_ids": [Command.set([cls.requester.id])],
            "chantier_region": "Casablanca-Settat", "work_type": "construction",
            "date_start": date(2026, 1, 1), "date": date(2026, 12, 31),
        })
        cls.chantier.action_approve_chantier()
        cls.chantier.action_initialize_chantier()
        cls.chantier.action_start_chantier()
        cls.product = cls.env["product.product"].create({"name": "Consumption Cement", "type": "product"})
        cls.env["stock.quant"]._update_available_quantity(cls.product, cls.chantier.site_location_id, 10)

    @classmethod
    def _user(cls, name, login, group):
        return cls.env["res.users"].with_context(no_reset_password=True).create({
            "name": name, "login": login, "company_id": cls.company.id,
            "company_ids": [Command.set([cls.company.id])],
            "groups_id": [Command.set([cls.env.ref("base.group_user").id, cls.env.ref(group).id])],
        })

    def test_two_person_approval_consumes_exact_site_stock(self):
        consumption = self.env["chantier.material.consumption"].with_user(self.requester).create({
            "chantier_id": self.chantier.id, "work_type": "construction",
            "line_ids": [Command.create({"product_id": self.product.id, "product_uom_qty": 4})],
        })
        consumption.with_user(self.requester).action_submit()
        with self.assertRaises(AccessError):
            consumption.with_user(self.requester).action_approve_and_consume()
        consumption.with_user(self.approver).action_approve_and_consume()
        self.assertEqual(consumption.state, "done")
        self.assertEqual(consumption.picking_id.state, "done")
        self.assertEqual(consumption.picking_id.chantier_consumption_id, consumption)
        remaining = self.env["stock.quant"]._get_available_quantity(self.product, self.chantier.site_location_id, strict=True)
        self.assertEqual(remaining, 6)
        with self.assertRaises(AccessError):
            consumption.line_ids.with_user(self.approver).write({"product_uom_qty": 9})

    def test_create_cannot_forge_consumption_evidence(self):
        with self.assertRaises(UserError):
            self.env["chantier.material.consumption"].with_context(
                elmokrif_consumption_workflow=True
            ).create({
                "chantier_id": self.chantier.id, "work_type": "construction",
                "state": "done", "approved_by_id": self.env.user.id,
            })
