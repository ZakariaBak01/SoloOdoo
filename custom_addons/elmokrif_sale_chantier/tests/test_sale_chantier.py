from datetime import date

from odoo.exceptions import UserError, ValidationError
from odoo.tests import TransactionCase, tagged


@tagged("post_install", "-at_install")
class TestSaleChantier(TransactionCase):
    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.company = cls.env.company
        cls.partner = cls.env["res.partner"].create({"name": "Chantier Customer"})
        cls.product = cls.env["product.product"].create(
            {
                "name": "Chantier Service",
                "type": "service",
                "list_price": 100,
            }
        )
        cls.warehouse = cls.env["stock.warehouse"].search(
            [("company_id", "=", cls.company.id)], limit=1
        )
        if not cls.warehouse:
            cls.warehouse = cls.env["stock.warehouse"].create(
                {
                    "name": "Sale Chantier Warehouse",
                    "code": "SCW",
                    "company_id": cls.company.id,
                }
            )

    def _create_chantier(self, name="Sales Chantier", **values):
        values.update(
            {
                "name": name,
                "is_chantier": True,
                "company_id": self.company.id,
                "warehouse_id": self.warehouse.id,
                "partner_id": self.partner.id,
                "site_partner_id": self.partner.id,
                "chantier_region": "Casablanca-Settat",
                "work_type": "construction",
                "date_start": date(2026, 1, 1),
                "date": date(2026, 12, 31),
            }
        )
        chantier = self.env["project.project"].create(values)
        chantier.action_approve_chantier()
        chantier.action_initialize_chantier()
        chantier.action_start_chantier()
        return chantier

    def _create_order(self, chantier):
        return self.env["sale.order"].create(
            {
                "partner_id": self.partner.id,
                "company_id": self.company.id,
                "chantier_id": chantier.id,
                "order_line": [
                    (
                        0,
                        0,
                        {
                            "product_id": self.product.id,
                            "product_uom_qty": 1,
                        },
                    )
                ],
            }
        )

    def test_confirmation_requires_initialized_in_progress_chantier(self):
        chantier = self.env["project.project"].create(
            {
                "name": "Not Initialized",
                "is_chantier": True,
                "company_id": self.company.id,
                "warehouse_id": self.warehouse.id,
                "partner_id": self.partner.id,
                "site_partner_id": self.partner.id,
                "chantier_region": "Casablanca-Settat",
                "work_type": "construction",
                "date_start": date(2026, 1, 1),
                "date": date(2026, 12, 31),
            }
        )
        order = self._create_order(chantier)
        with self.assertRaises(UserError):
            order.action_confirm()

    def test_line_chantier_is_propagated_to_invoice_line(self):
        chantier = self._create_chantier()
        order = self._create_order(chantier)
        order.action_confirm()
        invoice = order._create_invoices()
        invoice_line = invoice.invoice_line_ids.filtered(
            lambda line: line.sale_line_id
        )[:1]
        self.assertEqual(invoice_line.chantier_id, chantier)
        self.assertEqual(invoice_line.chantier_origin_id, chantier)
        self.assertEqual(invoice_line.sale_line_id.order_id, order)

    def test_customer_mismatch_is_rejected(self):
        chantier = self._create_chantier()
        other_partner = self.env["res.partner"].create({"name": "Other Customer"})
        with self.assertRaises(ValidationError):
            self.env["sale.order"].create(
                {
                    "partner_id": other_partner.id,
                    "company_id": self.company.id,
                    "chantier_id": chantier.id,
                }
            )
