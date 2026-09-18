import base64
from datetime import timedelta

from odoo import fields
from odoo.exceptions import AccessError, UserError
from odoo.tests.common import TransactionCase, tagged


@tagged("post_install", "-at_install")
class TestConstructionControl(TransactionCase):
    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.today = fields.Date.today()
        cls.customer = cls.env["res.partner"].create({
            "name": "Control Test Customer", "customer_rank": 1,
        })
        cls.chantier = cls.env["project.project"].create({
            "name": "Construction Control Test", "is_chantier": True,
            "company_id": cls.env.company.id, "partner_id": cls.customer.id,
            "user_id": cls.env.user.id,
        })
        cls.evidence = cls.env["ir.attachment"].create({
            "name": "evidence.txt", "datas": base64.b64encode(b"controlled evidence"),
            "mimetype": "text/plain",
        })

    def test_work_package_requires_readiness_and_closes_after_acceptance(self):
        package = self.env["construction.work.package"].create({
            "title": "Foundation concrete", "chantier_id": self.chantier.id,
            "company_id": self.env.company.id, "manager_id": self.env.user.id,
            "responsible_id": self.env.user.id, "planned_start": self.today,
            "planned_finish": self.today + timedelta(days=3), "planned_quantity": 10,
        })
        with self.assertRaises(UserError):
            package.action_mark_ready()
        package.write({
            "method_statement_ready": True, "drawings_ready": True,
            "permits_ready": True, "materials_ready": True,
        })
        package.action_mark_ready()
        package.action_release()
        package.action_start()
        package.installed_quantity = 10
        package.action_submit_inspection()
        package.action_accept()
        package.action_close()
        self.assertEqual(package.state, "closed")
        self.assertEqual(package.progress_percent, 100)

    def test_rfi_has_controlled_auditable_lifecycle(self):
        rfi = self.env["construction.rfi"].create({
            "title": "Confirm reinforcement lap", "chantier_id": self.chantier.id,
            "company_id": self.env.company.id, "responsible_id": self.env.user.id,
            "question": "Confirm the lap length at grid A1.",
            "response_due": self.today + timedelta(days=2),
        })
        with self.assertRaises(AccessError):
            rfi.write({"state": "closed"})
        rfi.action_submit()
        rfi.action_review()
        rfi.answer = "Use the approved structural detail S-101."
        rfi.action_answer()
        rfi.action_close()
        self.assertEqual(rfi.state, "closed")
        self.assertTrue(rfi.submitted_at and rfi.answered_at and rfi.closed_at)

    def test_change_event_creates_one_variation_with_live_project_impact(self):
        event = self.env["construction.change.event"].create({
            "title": "Additional excavation", "chantier_id": self.chantier.id,
            "company_id": self.env.company.id, "reason": "site_condition",
            "description": "Rock encountered below formation level.",
            "owner_id": self.env.user.id, "estimated_cost_impact": 1000,
            "estimated_revenue_impact": 1400,
            "attachment_ids": [(6, 0, self.evidence.ids)],
        })
        event.action_submit()
        event.action_estimate()
        event.action_review()
        event.action_accept()
        event.action_create_variation()
        variation = event.variation_order_id
        variation.attachment_ids = self.evidence
        variation.action_submit()
        variation.action_request_customer_approval()
        variation.customer_approval_reference = "CLIENT-APPROVAL-01"
        variation.action_approve()
        self.assertEqual(variation.state, "approved")
        self.assertEqual(self.chantier.approved_variation_cost, 1000)
        self.assertEqual(self.chantier.approved_variation_revenue, 1400)
        event.action_create_variation()
        self.assertEqual(len(event.variation_order_id), 1)
