from datetime import date

from odoo.exceptions import UserError
from odoo.tests import TransactionCase, tagged


@tagged("post_install", "-at_install")
class TestChantierCrm(TransactionCase):
    def test_quotation_keeps_explicit_opportunity_chantier(self):
        customer = self.env["res.partner"].create({
            "name": "Customer with multiple sites",
            "customer_rank": 1,
        })
        site_addresses = self.env["res.partner"].create([
            {"name": "Site A Address", "parent_id": customer.id, "type": "delivery"},
            {"name": "Site B Address", "parent_id": customer.id, "type": "delivery"},
        ])
        sites = self.env["project.project"].create([
            {"name": "Site A", "is_chantier": True, "company_id": self.env.company.id,
             "partner_id": customer.id, "site_partner_id": site_addresses[0].id},
            {"name": "Site B", "is_chantier": True, "company_id": self.env.company.id,
             "partner_id": customer.id, "site_partner_id": site_addresses[1].id},
        ])
        lead = self.env["crm.lead"].create({
            "name": "Quotation for Site B", "partner_id": customer.id,
            "company_id": self.env.company.id, "chantier_id": sites[1].id,
        })
        action = lead.action_new_quotation()
        order_model = self.env["sale.order"].with_context(action["context"])
        order = order_model.create(order_model.default_get(["partner_id", "company_id", "chantier_id", "opportunity_id"]))
        self.assertEqual(order.chantier_id, sites[1])
        self.assertEqual(order.opportunity_id, lead)

    def test_qualification_requires_complete_positive_business_data(self):
        customer = self.env["res.partner"].create({"name": "CRM Customer"})
        decision_maker = self.env["res.partner"].create({"name": "CRM Decision Maker"})
        lead = self.env["crm.lead"].create({
            "name": "Qualified construction opportunity", "type": "opportunity",
            "partner_id": customer.id, "chantier_work_type": "construction",
            "chantier_site_address": "123 Test Site", "chantier_region": "Rabat-Sale-Kenitra",
            "chantier_contract_value": 0, "chantier_expected_start": date(2026, 10, 1),
            "chantier_decision_maker_id": decision_maker.id, "chantier_next_action": "Visit site",
        })
        self.assertFalse(lead.chantier_qualification_complete)
        with self.assertRaises(UserError):
            lead.action_chantier_mark_qualified()
        lead.chantier_contract_value = 250000
        self.assertTrue(lead.chantier_qualification_complete)
        lead.action_chantier_mark_qualified()
        self.assertTrue(lead.message_ids.filtered(lambda message: "qualification completed" in (message.body or "").lower()))
