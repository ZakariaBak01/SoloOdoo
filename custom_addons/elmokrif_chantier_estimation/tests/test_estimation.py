from odoo.exceptions import AccessError
from odoo.tests import TransactionCase, tagged


@tagged("post_install", "-at_install")
class TestChantierEstimation(TransactionCase):
    def test_quantities_costs_tax_logistics_and_phases(self):
        chantier = self.env["project.project"].create({"name": "Estimate site", "is_chantier": True, "company_id": self.env.company.id})
        tax = self.env["account.tax"].create({"name": "VAT 20", "amount_type": "percent", "amount": 20, "type_tax_use": "purchase", "company_id": self.env.company.id})
        estimate = self.env["chantier.estimation"].create({"name": "Slab", "chantier_id": chantier.id, "length": 10, "width": 5, "depth": .2, "wastage_percent": 5, "cement_bag_cost": 80, "sand_cost_m3": 150, "gravel_cost_m3": 200, "water_cost_litre": .02, "labor_hourly_cost": 30, "machinery_daily_cost": 500, "truck_trip_cost": 300, "tax_id": tax.id, "foundation_percent": 60, "superstructure_percent": 30, "finishing_percent": 10, "manual_progress_percent": 25, "actual_labor_hours": 10, "actual_machinery_cost": 400})
        self.assertEqual(estimate.net_volume, 10)
        self.assertEqual(estimate.adjusted_volume, 10.5)
        self.assertEqual(estimate.truck_trips, 2)
        self.assertGreater(estimate.material_cost, 0)
        self.assertGreater(estimate.tax_amount, 0)
        self.assertAlmostEqual(estimate.foundation_cost + estimate.superstructure_cost + estimate.finishing_cost, estimate.total_cost, places=2)
        self.assertEqual(estimate.progress_percent, 25)
        self.assertEqual(estimate.actual_labor_cost, 300)
        self.assertEqual(estimate.actual_cost, 700)
        self.assertGreater(estimate.budget_consumed_percent, 0)

    def test_creating_revision_opens_a_new_draft(self):
        chantier = self.env["project.project"].create({
            "name": "Revision site",
            "is_chantier": True,
            "company_id": self.env.company.id,
        })
        estimate = self.env["chantier.estimation"].create({
            "name": "Approved baseline",
            "chantier_id": chantier.id,
            "length": 10,
            "width": 5,
            "depth": 0.2,
        })
        estimate.action_submit()
        estimate.action_approve()

        action = estimate.action_new_revision()
        revision = self.env["chantier.estimation"].browse(action["res_id"])

        self.assertEqual(action["type"], "ir.actions.act_window")
        self.assertEqual(action["res_model"], "chantier.estimation")
        self.assertEqual(action["target"], "current")
        self.assertTrue(revision.exists())
        self.assertEqual(revision.state, "draft")
        self.assertEqual(revision.revision_of_id, estimate)
        self.assertEqual(estimate.state, "approved")

        repeated_action = estimate.action_new_revision()
        self.assertEqual(repeated_action["res_id"], revision.id)

        revision.action_submit()
        revision.action_approve()
        self.assertEqual(revision.state, "approved")
        self.assertEqual(estimate.state, "superseded")

    def test_workflow_evidence_cannot_be_forged(self):
        chantier = self.env["project.project"].create({
            "name": "Protected estimate site",
            "is_chantier": True,
            "company_id": self.env.company.id,
        })
        estimate = self.env["chantier.estimation"].create({
            "name": "Protected baseline",
            "chantier_id": chantier.id,
            "length": 10,
            "width": 5,
            "depth": 0.2,
        })
        with self.assertRaises(AccessError):
            estimate.write({"state": "approved"})
        with self.assertRaises(AccessError):
            self.env["chantier.estimation"].create({
                "name": "Forged approved estimate",
                "chantier_id": chantier.id,
                "length": 10,
                "width": 5,
                "depth": 0.2,
                "state": "approved",
                "approved_by_id": self.env.user.id,
            })
