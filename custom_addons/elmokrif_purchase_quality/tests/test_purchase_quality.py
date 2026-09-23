from datetime import date

from odoo import Command
from odoo.exceptions import AccessError, UserError
from odoo.tests import TransactionCase, tagged

from ..models.workflow import QUALITY_WORKFLOW_TOKEN


@tagged("post_install", "-at_install")
class TestPurchaseQuality(TransactionCase):
    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.company = cls.env.company
        cls.company.write({
            "chantier_purchase_approval_threshold": 10000,
            "chantier_purchase_two_person": True,
            "chantier_quality_required": True,
        })
        cls.warehouse = cls.env["stock.warehouse"].search(
            [("company_id", "=", cls.company.id)], limit=1
        ) or cls.env["stock.warehouse"].create({
            "name": "Purchase Quality Warehouse",
            "code": "PQW",
            "company_id": cls.company.id,
        })
        cls.warehouse._ensure_chantier_quality_locations()
        cls.vendor = cls.env["res.partner"].create({
            "name": "Quality Material Vendor",
            "supplier_rank": 1,
        })
        cls.product = cls.env["product.product"].create({
            "name": "Quality Cement",
            "type": "product",
            "standard_price": 50,
        })
        cls.buyer = cls._create_user(
            "Pilot Buyer",
            "pilot_buyer@example.test",
            ["elmokrif_purchase_quality.group_chantier_purchase_buyer"],
        )
        cls.approver = cls._create_user(
            "Pilot Purchase Approver",
            "pilot_approver@example.test",
            ["elmokrif_purchase_quality.group_chantier_purchase_approver"],
        )
        cls.inspector = cls._create_user(
            "Pilot Quality Inspector",
            "pilot_quality@example.test",
            ["elmokrif_purchase_quality.group_chantier_quality_inspector"],
        )
        cls.storekeeper = cls._create_user(
            "Pilot Storekeeper",
            "pilot_storekeeper@example.test",
            ["stock.group_stock_user"],
        )
        cls.chantier = cls.env["project.project"].with_context(
            default_is_chantier=True
        ).create({
            "name": "Purchase Quality Chantier",
            "is_chantier": True,
            "company_id": cls.company.id,
            "warehouse_id": cls.warehouse.id,
            "partner_id": cls.env["res.partner"].create({
                "name": "Pilot Customer",
                "customer_rank": 1,
            }).id,
            "user_id": cls.env.user.id,
            "chantier_member_ids": [Command.set([cls.buyer.id, cls.approver.id, cls.inspector.id])],
            "date_start": date(2026, 1, 1),
            "date": date(2026, 12, 31),
            "chantier_region": "Marrakech-Safi",
            "work_type": "construction",
            "site_partner_id": cls.env["res.partner"].create({
                "name": "Pilot Site",
                "type": "other",
            }).id,
        })
        cls.chantier.action_approve_chantier()
        cls.chantier.action_initialize_chantier()
        cls.chantier.action_start_chantier()

    @classmethod
    def _create_user(cls, name, login, group_xmlids):
        return cls.env["res.users"].with_context(no_reset_password=True).create({
            "name": name,
            "login": login,
            "company_id": cls.company.id,
            "company_ids": [Command.set([cls.company.id])],
            "groups_id": [Command.set([
                cls.env.ref("base.group_user").id,
                *[cls.env.ref(xmlid).id for xmlid in group_xmlids],
            ])],
        })

    def _request(self, quantity=10):
        return self.env["chantier.material.request"].create({
            "chantier_id": self.chantier.id,
            "vendor_id": self.vendor.id,
            "required_date": date(2026, 3, 1),
            "justification": "Pilot procurement",
            "line_ids": [Command.create({
                "product_id": self.product.id,
                "product_uom_qty": quantity,
            })],
        })

    def _order(self, amount):
        request = self._request(quantity=1)
        return self.env["purchase.order"].with_user(self.buyer).create({
            "partner_id": self.vendor.id,
            "company_id": self.company.id,
            "picking_type_id": self.warehouse.in_type_id.id,
            "chantier_material_request_id": request.id,
            "order_line": [Command.create({
                "product_id": self.product.id,
                "name": self.product.display_name,
                "product_qty": 1,
                "product_uom": self.product.uom_po_id.id,
                "price_unit": amount,
                "date_planned": "2026-03-01 12:00:00",
                "chantier_material_request_line_id": request.line_ids.id,
            })],
        })

    def test_chantier_user_can_read_fulfillment_totals_after_submit(self):
        requester = self._create_user(
            "Restricted Requester",
            "restricted_requester@example.test",
            ["elmokrif_chantier.group_chantier_user"],
        )
        self.chantier.write({"chantier_member_ids": [Command.link(requester.id)]})
        request = self._request()

        request.with_user(requester).action_submit()
        line_values = request.with_user(requester).line_ids.read([
            "delivered_qty",
            "central_available_qty",
            "reserved_qty",
            "procurement_qty",
            "outstanding_qty",
            "suggested_fulfillment",
        ])[0]

        self.assertEqual(request.state, "submitted")
        self.assertEqual(line_values["delivered_qty"], 0.0)
        self.assertEqual(line_values["reserved_qty"], 0.0)
        self.assertEqual(line_values["procurement_qty"], 0.0)
        self.assertEqual(line_values["outstanding_qty"], 10.0)

    def test_purchase_threshold_inclusive_and_two_person_approval(self):
        below = self._order(9999)
        below.button_confirm()
        self.assertEqual(below.state, "purchase")

        equal = self._order(10000)
        equal.button_confirm()
        self.assertEqual(equal.state, "to approve")
        with self.assertRaises(AccessError):
            equal.button_approve()
        equal.with_user(self.approver).button_approve()
        self.assertEqual(equal.state, "purchase")
        self.assertEqual(equal.chantier_approved_by_id, self.approver)

        above = self._order(10001)
        above.button_confirm()
        self.assertEqual(above.state, "to approve")

    def test_public_context_cannot_forge_purchase_approval_evidence(self):
        order = self._order(10000)
        with self.assertRaises(AccessError):
            self.env["purchase.order"].with_context(skip_chantier_reapproval=True).create({
                "partner_id": self.vendor.id,
                "chantier_approved_by_id": self.buyer.id,
                "chantier_approved_amount": 10000,
            })
        with self.assertRaises(AccessError):
            order.with_user(self.buyer).with_context(skip_chantier_reapproval=True).write({
                "chantier_approved_by_id": self.buyer.id,
                "chantier_approved_amount": 10000,
            })

    def test_public_context_cannot_forge_quality_approval(self):
        request = self._request()
        receipt = self.env["stock.picking"].create({
            "picking_type_id": self.warehouse.in_type_id.id,
            "location_id": self.env.ref("stock.stock_location_suppliers").id,
            "location_dest_id": self.warehouse.chantier_input_location_id.id,
        })
        inspection = self.env["chantier.quality.inspection"].with_user(
            self.inspector
        ).with_context(_quality_workflow_token=QUALITY_WORKFLOW_TOKEN).create({
            "receipt_id": receipt.id,
            "company_id": self.company.id,
            "warehouse_id": self.warehouse.id,
            "chantier_id": request.chantier_id.id,
        })
        with self.assertRaises(UserError):
            inspection.with_user(self.inspector).with_context(
                _quality_workflow_token=None, quality_workflow=True
            ).write({
                "state": "approved"
            })
        with self.assertRaises(UserError):
            self.env["chantier.quality.inspection"].with_context(quality_workflow=True).create({
                "receipt_id": receipt.id, "company_id": self.company.id,
                "warehouse_id": self.warehouse.id, "chantier_id": request.chantier_id.id,
                "state": "approved", "inspector_id": self.inspector.id,
            })
        with self.assertRaises(AccessError):
            receipt.with_context(chantier_quality_release=True).write({
                "chantier_quality_release_kind": "accepted",
            })

    def test_buyer_who_is_approver_cannot_self_approve(self):
        self.buyer.write({
            "groups_id": [Command.link(
                self.env.ref("elmokrif_purchase_quality.group_chantier_purchase_approver").id
            )]
        })
        order = self._order(12000)
        order.button_confirm()
        with self.assertRaises(UserError):
            order.with_user(self.buyer).button_approve()

    def test_approved_purchase_cannot_be_changed(self):
        order = self._order(10000)
        order.button_confirm()
        order.with_user(self.approver).button_approve()
        with self.assertRaises(UserError):
            order.order_line.write({"price_unit": 10001})
        with self.assertRaises(UserError):
            order.write({"partner_id": self.vendor.id})

    def test_cross_company_request_link_is_rejected(self):
        other_company = self.env["res.company"].create({
            "name": "Other Purchase Company",
            "currency_id": self.company.currency_id.id,
        })
        allowed_companies = [self.company.id, other_company.id]
        other_warehouse = self.env["stock.warehouse"].with_context(
            allowed_company_ids=allowed_companies
        ).create({
            "name": "Other Company Warehouse",
            "code": "OCW",
            "company_id": other_company.id,
        })
        request = self._request(quantity=1)
        with self.assertRaises(UserError):
            self.env["purchase.order"].with_context(
                allowed_company_ids=allowed_companies
            ).create({
                "partner_id": self.vendor.id,
                "company_id": other_company.id,
                "picking_type_id": other_warehouse.in_type_id.id,
                "chantier_material_request_id": request.id,
            })

    def test_request_splits_stock_and_purchase_shortage(self):
        self.env["stock.quant"]._update_available_quantity(
            self.product, self.warehouse.lot_stock_id, 40
        )
        request = self._request(quantity=240)
        request.action_submit()
        request.action_approve()
        request.action_plan_fulfillment()

        self.assertEqual(request.picking_id.move_ids.product_uom_qty, 40)
        self.assertEqual(request.picking_id.state, "assigned")
        self.assertEqual(request.purchase_order_id.order_line.product_qty, 200)
        self.assertEqual(
            request.purchase_order_id.order_line.chantier_material_request_line_id,
            request.line_ids,
        )
        self.assertEqual(request.line_ids.reserved_qty, 40)
        self.assertEqual(request.line_ids.procurement_qty, 200)
        with self.assertRaises(UserError):
            request.action_plan_fulfillment()

        request.picking_id.move_ids.quantity = 40
        request.picking_id.move_ids.picked = True
        request.picking_id.button_validate()
        self.assertEqual(request.state, "partially_delivered")
        self.env["stock.quant"]._update_available_quantity(
            self.product, self.warehouse.lot_stock_id, 50
        )
        first_purchase_order = request.purchase_order_id
        request.action_plan_fulfillment()
        self.assertEqual(len(request.picking_ids), 2)
        self.assertEqual(request.purchase_order_id, first_purchase_order)
        self.assertEqual(
            (request.picking_ids - request.picking_id).move_ids.product_uom_qty,
            50,
        )

    def test_approved_request_cannot_create_commitment_while_chantier_on_hold(self):
        request = self._request(quantity=1)
        request.action_submit()
        request.action_approve()
        self.chantier.sudo().action_hold_chantier()
        with self.assertRaises(UserError):
            request.action_plan_fulfillment()
        self.assertFalse(request.picking_ids)
        self.assertFalse(request.purchase_order_id)

    def test_quality_partial_release_and_direct_bypass(self):
        order = self._order(500)
        order.button_confirm()
        receipt = order.picking_ids
        self.assertEqual(receipt.location_dest_id, self.warehouse.chantier_input_location_id)
        receipt.action_confirm()
        for move in receipt.move_ids:
            move.quantity = 1
            move.picked = True
        receipt.button_validate()

        inspection = receipt.chantier_quality_inspection_id
        self.assertTrue(inspection)
        self.assertEqual(
            inspection.with_user(self.storekeeper).read(["state"])[0]["state"],
            "draft",
        )
        self.assertEqual(
            inspection.with_user(self.storekeeper).line_ids.read(["received_qty"])[0]["received_qty"],
            1,
        )
        with self.assertRaises(AccessError):
            inspection.with_user(self.storekeeper).action_approve_and_release()
        self.assertEqual(receipt.chantier_quality_transfer_id.state, "done")
        self.assertEqual(
            receipt.chantier_quality_transfer_id.location_id,
            self.warehouse.chantier_input_location_id,
        )
        self.assertEqual(
            receipt.chantier_quality_transfer_id.location_dest_id,
            self.warehouse.chantier_quality_location_id,
        )
        inspection.line_ids.with_user(self.inspector).write({
            "accepted_qty": 0.8,
            "rejected_qty": 0.2,
            "condition_ok": True,
            "specification_ok": True,
            "rejection_reason": "Damaged packaging",
        })
        inspection.with_user(self.inspector).action_approve_and_release()
        self.assertEqual(inspection.state, "approved")
        self.assertEqual(
            self.env["stock.quant"]._get_available_quantity(
                self.product, self.warehouse.lot_stock_id, strict=True
            ),
            0.8,
        )
        self.assertEqual(
            self.env["stock.quant"]._get_available_quantity(
                self.product, self.warehouse.chantier_quarantine_location_id, strict=True
            ),
            0.2,
        )
        with self.assertRaises(UserError):
            inspection.with_user(self.inspector).action_approve_and_release()

        bypass = self.env["stock.picking"].create({
            "picking_type_id": self.warehouse.int_type_id.id,
            "location_id": self.warehouse.chantier_quality_location_id.id,
            "location_dest_id": self.warehouse.lot_stock_id.id,
            "move_ids_without_package": [Command.create({
                "name": self.product.display_name,
                "product_id": self.product.id,
                "product_uom_qty": 1,
                "product_uom": self.product.uom_id.id,
                "location_id": self.warehouse.chantier_quality_location_id.id,
                "location_dest_id": self.warehouse.lot_stock_id.id,
            })],
        })
        with self.assertRaises(UserError):
            bypass.button_validate()

        input_bypass = self.env["stock.picking"].create({
            "picking_type_id": self.warehouse.int_type_id.id,
            "location_id": self.warehouse.chantier_input_location_id.id,
            "location_dest_id": self.warehouse.lot_stock_id.id,
            "move_ids_without_package": [Command.create({
                "name": self.product.display_name,
                "product_id": self.product.id,
                "product_uom_qty": 1,
                "product_uom": self.product.uom_id.id,
                "location_id": self.warehouse.chantier_input_location_id.id,
                "location_dest_id": self.warehouse.lot_stock_id.id,
            })],
        })
        with self.assertRaises(UserError):
            input_bypass.button_validate()

    def test_quality_release_preserves_lot_for_accepted_and_rejected_stock(self):
        self.product.tracking = "lot"
        request = self._request(quantity=10)
        request.action_submit()
        request.action_approve()
        order = self.env["purchase.order"].with_user(self.buyer).create({
            "partner_id": self.vendor.id,
            "company_id": self.company.id,
            "picking_type_id": self.warehouse.in_type_id.id,
            "chantier_material_request_id": request.id,
            "order_line": [Command.create({
                "product_id": self.product.id,
                "name": self.product.display_name,
                "product_qty": 10,
                "product_uom": self.product.uom_po_id.id,
                "price_unit": 100,
                "date_planned": "2026-03-01 12:00:00",
                "chantier_material_request_line_id": request.line_ids.id,
            })],
        })
        request.purchase_order_id = order
        order.button_confirm()
        receipt = order.picking_ids
        receipt.action_confirm()
        lot = self.env["stock.lot"].create({
            "name": "LOT-QA-10",
            "product_id": self.product.id,
            "company_id": self.company.id,
        })
        receipt.move_ids.quantity = 10
        receipt.move_ids.picked = True
        receipt.move_ids.move_line_ids.write({"lot_id": lot.id})
        receipt.button_validate()

        inspection = receipt.chantier_quality_inspection_id
        self.assertEqual(inspection.line_ids.lot_id, lot)
        inspection.line_ids.with_user(self.inspector).write({
            "accepted_qty": 8,
            "rejected_qty": 2,
            "condition_ok": True,
            "specification_ok": True,
            "rejection_reason": "Two units damaged",
        })
        inspection.with_user(self.inspector).action_approve_and_release()

        self.assertEqual(
            self.env["stock.quant"]._get_available_quantity(
                self.product,
                self.warehouse.lot_stock_id,
                lot_id=lot,
                strict=True,
            ),
            8,
        )
        self.assertEqual(
            self.env["stock.quant"]._get_available_quantity(
                self.product,
                self.warehouse.chantier_quarantine_location_id,
                lot_id=lot,
                strict=True,
            ),
            2,
        )
        self.assertEqual(
            inspection.accepted_picking_id.move_ids.move_line_ids.lot_id, lot
        )
        self.assertEqual(
            inspection.rejected_picking_id.move_ids.move_line_ids.lot_id, lot
        )

        request.action_plan_fulfillment()
        self.assertEqual(request.picking_ids.move_ids.product_uom_qty, 8)
        self.assertEqual(request.picking_ids.state, "assigned")

        return_action = inspection.with_user(self.buyer).action_create_supplier_return()
        supplier_return = self.env["stock.picking"].browse(return_action["res_id"])
        supplier_return.action_confirm()
        supplier_return.action_assign()
        for move in supplier_return.move_ids:
            if not move.move_line_ids:
                move.quantity = move.product_uom_qty
            move.picked = True
        supplier_return.button_validate()
        order.order_line.invalidate_recordset(["qty_received"])
        self.assertEqual(supplier_return.state, "done")
        self.assertEqual(supplier_return.return_id, receipt)
        self.assertEqual(
            supplier_return.move_ids.origin_returned_move_id, receipt.move_ids
        )
        self.assertEqual(supplier_return.move_ids.move_line_ids.lot_id, lot)
        self.assertEqual(order.order_line.qty_received, 8)
        self.assertEqual(
            self.env["stock.quant"]._get_available_quantity(
                self.product,
                self.warehouse.chantier_quarantine_location_id,
                lot_id=lot,
                strict=True,
            ),
            0,
        )
        with self.assertRaises(UserError):
            inspection.with_user(self.buyer).action_create_supplier_return()
