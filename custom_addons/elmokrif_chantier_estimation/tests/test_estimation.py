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
