from datetime import date

from odoo.exceptions import AccessError, UserError, ValidationError
from odoo.tests import Form, TransactionCase, tagged


@tagged("post_install", "-at_install")
class TestChantierMaterialRequest(TransactionCase):
    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.company = cls.env.company
        cls.warehouse = cls.env["stock.warehouse"].search(
            [("company_id", "=", cls.company.id)], limit=1
        )
        if not cls.warehouse:
            cls.warehouse = cls.env["stock.warehouse"].create(
                {
                    "name": "Materials Test Warehouse",
                    "code": "MTW",
                    "company_id": cls.company.id,
                }
            )
        cls.product = cls.env["product.product"].create(
            {"name": "Test Cement", "type": "product"}
        )
        cls.env["stock.quant"]._update_available_quantity(
            cls.product, cls.warehouse.lot_stock_id, 1000
        )

    def _create_in_progress_chantier(self):
        chantier = self.env["project.project"].with_context(
            default_is_chantier=True
        ).create(
            {
                "name": "Materials Test Chantier",
                "is_chantier": True,
                "company_id": self.company.id,
                "warehouse_id": self.warehouse.id,
                "chantier_region": "Casablanca-Settat",
                "work_type": "construction",
                "partner_id": self.env["res.partner"].create(
                    {"name": "Materials Test Customer", "customer_rank": 1}
                ).id,
                "date_start": date(2026, 1, 1),
                "date": date(2026, 12, 31),
                "site_partner_id": self.env["res.partner"].create(
                    {"name": "Materials Test Site", "type": "other"}
                ).id,
            }
        )
        chantier.sudo().action_approve_chantier()
        chantier.sudo().action_initialize_chantier()
        chantier.sudo().action_start_chantier()
        return chantier

    def _create_request(self, chantier, product=None, quantity=10):
        product = product or self.product
        return self.env["chantier.material.request"].create(
            {
                "chantier_id": chantier.id,
                "line_ids": [
                    (0, 0, {"product_id": product.id, "product_uom_qty": quantity})
                ],
            }
        )

    def _create_and_approve_transfer(self, request):
        request.sudo().action_submit()
        request.sudo().action_approve()
        request.sudo().action_create_transfer()
        return request.picking_id

    def _validate_picking(self, picking, quantity):
        picking.action_confirm()
        picking.action_assign()
        self.assertIn(picking.state, ("assigned", "partially_available"))
        move = picking.move_ids
        self.assertTrue(move.move_line_ids)
        move.quantity = quantity
        move.picked = True
        action = picking.button_validate()
        if isinstance(action, dict) and action.get("res_model") == "stock.backorder.confirmation":
            wizard = Form(
                picking.env["stock.backorder.confirmation"].with_context(action["context"])
            ).save()
            wizard.process()
        return picking

    def _stockable_product(self, name, quantity=0, standard_price=0):
        product = self.env["product.product"].create({
            "name": name,
            "type": "product",
            "standard_price": standard_price,
        })
        if quantity:
            self.env["stock.quant"]._update_available_quantity(
                product, self.warehouse.lot_stock_id, quantity
            )
        return product

    def _create_chantier_user(self):
        return self.env["res.users"].with_context(no_reset_password=True).create(
            {
                "name": "Restricted chantier user",
                "login": "restricted_chantier_user",
                "email": "restricted@example.test",
                "groups_id": [
                    (6, 0, [
                        self.env.ref("base.group_user").id,
                        self.env.ref("elmokrif_chantier.group_chantier_user").id,
                    ]),
                ],
            }
        )

    def test_submitted_request_creates_site_delivery(self):
        chantier = self._create_in_progress_chantier()
        request = self._create_request(chantier)

        self._create_and_approve_transfer(request)

        self.assertEqual(request.state, "approved")
        self.assertTrue(request.picking_id)
        self.assertEqual(request.picking_id.chantier_id, chantier)
        self.assertEqual(request.picking_id.chantier_operation, "delivery")
        self.assertEqual(request.picking_id.location_id, self.warehouse.lot_stock_id)
        self.assertEqual(request.picking_id.location_dest_id, chantier.site_location_id)
        self.assertEqual(request.picking_id.move_ids.product_id, self.product)
        self.assertEqual(request.picking_id.move_ids.product_uom_qty, 10)

    def test_empty_request_cannot_be_submitted(self):
        chantier = self._create_in_progress_chantier()
        request = self.env["chantier.material.request"].create(
            {"chantier_id": chantier.id}
        )

        with self.assertRaises(UserError):
            request.sudo().action_submit()

    def test_create_cannot_skip_request_approval(self):
        chantier = self._create_in_progress_chantier()
        for state in ("submitted", "approved", "done"):
            with self.subTest(state=state):
                with self.assertRaises(UserError):
                    self.env["chantier.material.request"].create({
                        "chantier_id": chantier.id, "state": state,
                    })
                with self.assertRaises(UserError):
                    self.env["chantier.material.request"].with_context(default_state=state).create({
                        "chantier_id": chantier.id,
                    })

    def test_submitted_request_lines_cannot_be_added_moved_or_deleted(self):
        chantier = self._create_in_progress_chantier()
        submitted = self._create_request(chantier)
        draft = self._create_request(chantier)
        submitted.action_submit()
        with self.assertRaises(UserError):
            self.env["chantier.material.request.line"].create({
                "request_id": submitted.id, "product_id": self.product.id,
                "product_uom_qty": 100,
            })
        with self.assertRaises(UserError):
            draft.line_ids.write({"request_id": submitted.id})
        with self.assertRaises(UserError):
            submitted.line_ids.write({"request_id": draft.id})
        with self.assertRaises(UserError):
            submitted.line_ids.unlink()
        with self.assertRaises(UserError):
            submitted.unlink()

    def test_request_requires_chantier_in_progress(self):
        chantier = self._create_in_progress_chantier()
        chantier.sudo().action_hold_chantier()
        request = self._create_request(chantier)

        with self.assertRaises(UserError):
            request.sudo().action_submit()

    def test_consumption_uses_dedicated_valuation_location(self):
        chantier = self._create_in_progress_chantier()
        self.warehouse._ensure_chantier_operation_locations()
        loss_location = self.warehouse.chantier_consumption_location_id
        picking = self.env["stock.picking"].create(
            {
                "picking_type_id": self.warehouse.int_type_id.id,
                "chantier_id": chantier.id,
                "chantier_operation": "consumption",
                "location_id": chantier.site_location_id.id,
                "location_dest_id": loss_location.id,
            }
        )

        self.assertEqual(picking.location_id, chantier.site_location_id)
        self.assertEqual(picking.location_dest_id, loss_location)

    def test_manual_chantier_transfer_normalizes_delivery_order_defaults(self):
        chantier = self._create_in_progress_chantier()
        picking = self.env["stock.picking"].create({
            "picking_type_id": self.warehouse.out_type_id.id,
            "chantier_id": chantier.id,
            "chantier_operation": "delivery",
            "location_id": self.warehouse.lot_stock_id.id,
            "location_dest_id": self.warehouse.out_type_id.default_location_dest_id.id,
        })

        self.assertEqual(picking.picking_type_id, self.warehouse.int_type_id)
        self.assertEqual(picking.location_id, self.warehouse.lot_stock_id)
        self.assertEqual(picking.location_dest_id, chantier.site_location_id)

    def test_global_request_defaults_company_and_accepts_its_chantier(self):
        request = self.env["chantier.material.request"].new({})
        self.assertEqual(request.company_id, self.company)

        chantier = self._create_in_progress_chantier()
        request = self._create_request(chantier)
        self.assertEqual(request.company_id, chantier.company_id)

    def test_request_state_and_lines_cannot_be_bypassed(self):
        chantier = self._create_in_progress_chantier()
        request = self._create_request(chantier)
        user = self._create_chantier_user()
        chantier.sudo().write({"chantier_member_ids": [(4, user.id)]})

        request.with_user(user).action_submit()
        with self.assertRaises(AccessError):
            request.with_user(user).write({"state": "approved"})
        with self.assertRaises(UserError):
            request.with_user(user).line_ids.write({"product_uom_qty": 999})

    def test_negative_requested_quantity_is_rejected(self):
        chantier = self._create_in_progress_chantier()
        with self.assertRaises(ValidationError):
            self.env["chantier.material.request"].create(
                {
                    "chantier_id": chantier.id,
                    "line_ids": [(0, 0, {
                        "product_id": self.product.id,
                        "product_uom_qty": -1,
                    })],
                }
            )

    def test_received_quantity_is_limited_to_its_request(self):
        chantier = self._create_in_progress_chantier()
        product = self._stockable_product("Request receipt stock", quantity=10)
        first = self._create_request(chantier, product, quantity=4)
        second = self._create_request(chantier, product, quantity=6)
        self._validate_picking(self._create_and_approve_transfer(first), 4)
        self._validate_picking(self._create_and_approve_transfer(second), 6)

        self.assertEqual(first.line_ids.delivered_qty, 4)
        self.assertEqual(second.line_ids.delivered_qty, 6)

    def test_duplicate_product_lines_keep_exact_move_allocation(self):
        chantier = self._create_in_progress_chantier()
        product = self._stockable_product("Duplicate-line stock", quantity=10)
        request = self.env["chantier.material.request"].create({
            "chantier_id": chantier.id,
            "line_ids": [
                (0, 0, {"product_id": product.id, "product_uom_qty": 4}),
                (0, 0, {"product_id": product.id, "product_uom_qty": 6}),
            ],
        })
        picking = self._create_and_approve_transfer(request)

        picking.action_confirm()
        picking.action_assign()
        self.assertEqual(len(picking.move_ids), 2)
        self.assertEqual(
            picking.move_ids.mapped("material_request_line_id"), request.line_ids
        )
        for move in picking.move_ids:
            move.quantity = move.product_uom_qty
            move.picked = True
        picking.button_validate()

        self.assertEqual(request.state, "done")
        self.assertEqual(
            sorted(request.line_ids.mapped("delivered_qty")), [4, 6]
        )

    def test_short_delivery_without_backorder_remains_partial(self):
        chantier = self._create_in_progress_chantier()
        product = self._stockable_product("Short delivery stock", quantity=10)
        request = self._create_request(chantier, product, quantity=10)
        picking = self._create_and_approve_transfer(request)
        picking.action_confirm()
        picking.action_assign()
        picking.move_ids.quantity = 4
        picking.move_ids.picked = True
        action = picking.button_validate()
        wizard = Form(
            picking.env["stock.backorder.confirmation"].with_context(action["context"])
        ).save()
        wizard.process_cancel_backorder()

        self.assertEqual(picking.state, "done")
        self.assertEqual(request.line_ids.delivered_qty, 4)
        self.assertEqual(request.state, "partially_delivered")

    def test_backorder_keeps_material_request_link(self):
        chantier = self._create_in_progress_chantier()
        product = self._stockable_product("Partial delivery stock", quantity=10)
        request = self._create_request(chantier, product)
        picking = self._create_and_approve_transfer(request)
        self._validate_picking(picking, 4)
        backorder = picking.backorder_ids

        self.assertEqual(request.state, "partially_delivered")
        self.assertEqual(request.line_ids.delivered_qty, 4)
        self.assertEqual(backorder.material_request_id, request)
        self.assertEqual(backorder.chantier_id, chantier)
        self._validate_picking(backorder, 6)
        self.assertEqual(request.state, "done")
        self.assertEqual(request.line_ids.delivered_qty, 10)

    def test_company_rule_hides_requests_from_other_companies(self):
        chantier = self._create_in_progress_chantier()
        request = self._create_request(chantier)
        other_company = self.env["res.company"].create({"name": "Other request company"})
        user = self._create_chantier_user()
        user.write({
            "company_id": other_company.id,
            "company_ids": [(6, 0, [other_company.id])],
        })

        self.assertNotIn(
            request,
            self.env["chantier.material.request"].with_user(user).with_context(
                allowed_company_ids=[other_company.id]
            ).search([]),
        )
        with self.assertRaises(AccessError):
            request.with_user(user).with_context(
                allowed_company_ids=[other_company.id]
            ).write({"request_date": request.request_date})

    def test_assignment_rule_hides_another_chantiers_request(self):
        chantier = self._create_in_progress_chantier()
        request = self._create_request(chantier)
        user = self._create_chantier_user()

        visible = self.env["chantier.material.request"].with_user(user).search(
            [("id", "=", request.id)]
        )

        self.assertFalse(visible)
        with self.assertRaises(AccessError):
            request.with_user(user).write({"request_date": request.request_date})

    def test_preselected_chantier_sets_its_company(self):
        other_company = self.env["res.company"].create({"name": "Other chantier company"})
        other_warehouse = self.env["stock.warehouse"].create({
            "name": "Other chantier warehouse",
            "code": "OCW",
            "company_id": other_company.id,
        })
        other_chantier = self.env["project.project"].sudo().with_context(
            default_is_chantier=True
        ).create({
            "name": "Other-company chantier",
            "is_chantier": True,
            "company_id": other_company.id,
            "warehouse_id": other_warehouse.id,
            "chantier_region": "Rabat-Salé-Kénitra",
            "work_type": "construction",
            "site_partner_id": self.env["res.partner"].create({
                "name": "Other-company site", "type": "other"
            }).id,
        })

        request = self.env["chantier.material.request"].sudo().create({
            "chantier_id": other_chantier.id,
            "line_ids": [(0, 0, {
                "product_id": self.product.id,
                "product_uom_qty": 1,
            })],
        })

        self.assertEqual(request.company_id, other_company)
        self.assertEqual(
            other_chantier.action_view_material_requests()["context"]["default_company_id"],
            other_company.id,
        )

    def test_uom_summary_and_cost_use_the_chantier_company_price(self):
        other_company = self.env["res.company"].create({"name": "Cost company"})
        other_env = self.env["res.company"].sudo().with_context(
            allowed_company_ids=[self.company.id, other_company.id]
        ).with_company(other_company).env
        other_warehouse = other_env["stock.warehouse"].create({
            "name": "Cost warehouse",
            "code": "CST",
            "company_id": other_company.id,
        })
        chantier = other_env["project.project"].with_context(
            default_is_chantier=True
        ).create({
            "name": "Cost chantier",
            "is_chantier": True,
            "company_id": other_company.id,
            "warehouse_id": other_warehouse.id,
            "chantier_region": "Marrakesh-Safi",
            "work_type": "construction",
            "partner_id": other_env["res.partner"].create({
                "name": "Cost customer", "customer_rank": 1
            }).id,
            "date_start": date(2026, 1, 1),
            "date": date(2026, 12, 31),
            "site_partner_id": other_env["res.partner"].create({
                "name": "Cost site", "type": "other"
            }).id,
        })
        chantier.action_approve_chantier()
        chantier.action_initialize_chantier()
        chantier.action_start_chantier()
        product = self.env["product.product"].create({
            "name": "Dozen cost product",
            "type": "product",
            "standard_price": 10,
        })
        product.sudo().with_context(
            allowed_company_ids=[self.company.id, other_company.id]
        ).with_company(other_company).standard_price = 20
        dozen = self.env.ref("uom.product_uom_dozen")
        other_env["stock.quant"]._update_available_quantity(
            product, chantier.site_location_id, 12
        )
        other_warehouse._ensure_chantier_operation_locations()
        loss_location = other_warehouse.chantier_consumption_location_id
        picking = other_env["stock.picking"].create({
            "picking_type_id": other_warehouse.int_type_id.id,
            "chantier_id": chantier.id,
            "chantier_operation": "consumption",
            "location_id": chantier.site_location_id.id,
            "location_dest_id": loss_location.id,
            "move_ids_without_package": [(0, 0, {
                "name": product.display_name,
                "product_id": product.id,
                "product_uom_qty": 1,
                "product_uom": dozen.id,
                "location_id": chantier.site_location_id.id,
                "location_dest_id": loss_location.id,
            })],
        })
        self._validate_picking(picking, 1)
        chantier.invalidate_recordset(["material_cost", "material_summary"])

        self.assertEqual(chantier.material_cost, 240)
        self.assertIn("12.00", str(chantier.material_summary))
        self.assertEqual(picking.move_ids.chantier_valuation_status, "valued")

        product.sudo().with_context(
            allowed_company_ids=[self.company.id, other_company.id]
        ).with_company(other_company).standard_price = 75
        chantier.invalidate_recordset(["material_cost", "material_summary"])

        self.assertEqual(chantier.material_cost, 240)
