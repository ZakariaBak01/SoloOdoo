from odoo.exceptions import UserError, ValidationError
from odoo.tests import TransactionCase, tagged


@tagged("post_install", "-at_install")
class TestChantier(TransactionCase):
    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.company = cls.env.company
        cls.warehouse = cls.env["stock.warehouse"].search(
            [("company_id", "=", cls.company.id)], limit=1
        )
        if not cls.warehouse:
            cls.warehouse = cls.env["stock.warehouse"].create(
                {"name": "EL MOKRIF Test Warehouse", "code": "EMT", "company_id": cls.company.id}
            )

    def _create_chantier(self, **values):
        values.setdefault("name", "Test Chantier")
        values.setdefault("is_chantier", True)
        values.setdefault("company_id", self.company.id)
        values.setdefault("warehouse_id", self.warehouse.id)
        return self.env["project.project"].create(values)

    def test_initialize_is_idempotent(self):
        chantier = self._create_chantier()

        chantier.action_initialize_chantier()
        analytic_account = chantier.analytic_account_id
        site_location = chantier.site_location_id

        chantier.action_initialize_chantier()

        self.assertEqual(chantier.analytic_account_id, analytic_account)
        self.assertEqual(chantier.site_location_id, site_location)
        self.assertEqual(
            self.env["stock.location"].with_context(active_test=False).search_count(
                [("chantier_id", "=", chantier.id)]
            ),
            1,
        )

    def test_chantier_requires_company_consistency(self):
        other_company = self.env["res.company"].create({"name": "Other Company"})
        other_warehouse = self.env["stock.warehouse"].create(
            {"name": "Other Warehouse", "code": "OTH", "company_id": other_company.id}
        )

        with self.assertRaises(ValidationError):
            self._create_chantier(warehouse_id=other_warehouse.id)

    def test_chantier_uses_active_company_when_not_supplied(self):
        chantier = self.env["project.project"].with_context(
            default_is_chantier=True
        ).create(
            {"name": "Quick Create Chantier"}
        )

        self.assertEqual(chantier.company_id, self.company)

    def test_invalid_lifecycle_jump_is_rejected(self):
        chantier = self._create_chantier()

        with self.assertRaises(UserError):
            chantier.action_start_chantier()

    def test_initialized_location_cannot_be_replaced_manually(self):
        chantier = self._create_chantier()
        chantier.action_initialize_chantier()
        other_location = self.env["stock.location"].create(
            {
                "name": "Other Site Location",
                "location_id": self.warehouse.lot_stock_id.id,
                "usage": "internal",
                "company_id": self.company.id,
            }
        )

        with self.assertRaises(UserError):
            chantier.site_location_id = other_location
