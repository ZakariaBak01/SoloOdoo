from datetime import date

from odoo.exceptions import UserError
from odoo.tests import TransactionCase, tagged


@tagged("post_install", "-at_install", "elmokrif_system")
class TestChantierBusinessFlow(TransactionCase):
    """Guide CORE-01, SAL-01 and STK-02 across the installed bridges."""

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.company = cls.env.company
        cls.customer = cls.env["res.partner"].create(
            {"name": "EL MOKRIF System Test Customer"}
        )
        cls.site = cls.env["res.partner"].create(
            {
                "name": "EL MOKRIF System Test Site",
                "parent_id": cls.customer.id,
                "type": "delivery",
            }
        )
        cls.warehouse = cls.env["stock.warehouse"].search(
            [("company_id", "=", cls.company.id)], limit=1
        )
        cls.material = cls.env["product.product"].create(
            {
                "name": "System Test Material",
                "type": "product",
                "standard_price": 10,
            }
        )
        cls.service = cls.env["product.product"].create(
            {
                "name": "System Test Service",
                "type": "service",
                "list_price": 30000,
            }
        )

    def _validate(self, picking, quantity):
        picking.action_confirm()
        picking.action_assign()
        move = picking.move_ids
        move.quantity = quantity
        move.picked = True
        result = picking.button_validate()
        self.assertFalse(
            isinstance(result, dict)
            and result.get("res_model") == "stock.backorder.confirmation"
        )
        self.assertEqual(picking.state, "done")

    def _site_operation(self, chantier, operation, quantity):
        self.warehouse._ensure_chantier_operation_locations()
        source, destination = {
            "consumption": (
                chantier.site_location_id,
                self.warehouse.chantier_consumption_location_id,
            ),
            "missing": (
                chantier.site_location_id,
                self.warehouse.chantier_missing_location_id,
            ),
            "return": (chantier.site_location_id, self.warehouse.lot_stock_id),
        }[operation]
        picking = self.env["stock.picking"].create(
            {
                "picking_type_id": self.warehouse.int_type_id.id,
                "chantier_id": chantier.id,
                "chantier_operation": operation,
                "location_id": source.id,
                "location_dest_id": destination.id,
                "move_ids_without_package": [
                    (
                        0,
                        0,
                        {
                            "name": self.material.display_name,
                            "product_id": self.material.id,
                            "product_uom_qty": quantity,
                            "product_uom": self.material.uom_id.id,
                            "location_id": source.id,
                            "location_dest_id": destination.id,
                        },
                    )
                ],
            }
        )
        self._validate(picking, quantity)
        return picking

    def test_quote_invoice_materials_and_closeout(self):
        chantier = self.env["project.project"].with_context(
            default_is_chantier=True
        ).create(
            {
                "name": "CH-TEST-001",
                "is_chantier": True,
                "company_id": self.company.id,
                "partner_id": self.customer.id,
                "site_partner_id": self.site.id,
                "user_id": self.env.user.id,
                "warehouse_id": self.warehouse.id,
                "chantier_region": "Casablanca-Settat",
                "work_type": "construction",
                "date_start": date(2026, 1, 1),
                "date": date(2026, 12, 31),
            }
        )
        chantier.action_approve_chantier()
        first_account = chantier.analytic_account_id
        first_location = chantier.site_location_id
        chantier.action_initialize_chantier()
        self.assertEqual(chantier.analytic_account_id, first_account)
        self.assertEqual(chantier.site_location_id, first_location)
        chantier.action_start_chantier()

        order = self.env["sale.order"].create(
            {
                "partner_id": self.customer.id,
                "company_id": self.company.id,
                "chantier_id": chantier.id,
                "order_line": [(0, 0, {"product_id": self.service.id})],
            }
        )
        order.write({"state": "sent"})
        activity = order.chantier_followup_activity_id
        self.assertTrue(activity)
        order._schedule_first_chantier_followup()
        self.assertEqual(order.chantier_followup_activity_id, activity)
        order.action_confirm()
        self.assertFalse(activity.exists())
        invoice = order._create_invoices()
        commercial_line = invoice.invoice_line_ids.filtered("sale_line_id")[:1]
        self.assertEqual(invoice.chantier_id, chantier)
        self.assertEqual(commercial_line.chantier_id, chantier)
        self.assertEqual(
            commercial_line.analytic_distribution,
            {str(first_account.id): 100.0},
        )

        self.env["stock.quant"]._update_available_quantity(
            self.material, self.warehouse.lot_stock_id, 10
        )
        request = self.env["chantier.material.request"].create(
            {
                "chantier_id": chantier.id,
                "line_ids": [
                    (0, 0, {"product_id": self.material.id, "product_uom_qty": 10})
                ],
            }
        )
        request.action_submit()
        request.action_approve()
        request.action_create_transfer()
        self._validate(request.picking_id, 10)
        self.assertEqual(request.state, "done")

        self._site_operation(chantier, "consumption", 6)
        self._site_operation(chantier, "return", 2)
        chantier.action_complete_chantier()
        with self.assertRaises(UserError):
            chantier.action_close_chantier()
        self._site_operation(chantier, "missing", 2)
        chantier.invalidate_recordset(["material_cost", "material_summary"])
        self.assertEqual(chantier.material_cost, 80)
        self.assertEqual(
            self.env["stock.quant"]._get_available_quantity(
                self.material, chantier.site_location_id
            ),
            0,
        )
        pending_request = self.env["chantier.material.request"].create(
            {
                "chantier_id": chantier.id,
                "line_ids": [
                    (0, 0, {"product_id": self.material.id, "product_uom_qty": 1})
                ],
            }
        )
        with self.assertRaises(UserError):
            chantier.action_close_chantier()
        pending_request.action_cancel()
        chantier.action_close_chantier()
        self.assertEqual(chantier.chantier_state, "closed")
