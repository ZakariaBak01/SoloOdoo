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
            {"name": "Test Cement", "type": "consu"}
        )

    def _create_in_progress_chantier(self):
        chantier = self.env["project.project"].create(
            {
                "name": "Materials Test Chantier",
                "is_chantier": True,
                "company_id": self.company.id,
                "warehouse_id": self.warehouse.id,
                "chantier_region": "Casablanca-Settat",
                "work_type": "construction",
                "partner_id": self.env["res.partner"].create(
                    {"name": "Materials Test Customer"}
                ).id,
                "date_start": date(2026, 1, 1),
                "date": date(2026, 12, 31),
                "site_partner_id": self.env["res.partner"].create(
                    {"name": "Materials Test Site"}
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

    def test_request_requires_chantier_in_progress(self):
        chantier = self._create_in_progress_chantier()
        chantier.sudo().action_hold_chantier()
        request = self._create_request(chantier)

        with self.assertRaises(UserError):
            request.sudo().action_submit()

    def test_consumption_uses_inventory_adjustment_location(self):
        chantier = self._create_in_progress_chantier()
        loss_location = self.env["stock.location"].search(
            [("usage", "=", "inventory")], limit=1
        )
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
        chantier.sudo().write({"favorite_user_ids": [(4, user.id)]})

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

    def test_preselected_chantier_sets_its_company(self):
        other_company = self.env["res.company"].create({"name": "Other chantier company"})
        other_warehouse = self.env["stock.warehouse"].create({
            "name": "Other chantier warehouse",
            "code": "OCW",
            "company_id": other_company.id,
        })
        other_chantier = self.env["project.project"].sudo().create({
            "name": "Other-company chantier",
            "is_chantier": True,
            "company_id": other_company.id,
            "warehouse_id": other_warehouse.id,
            "chantier_region": "Rabat-Salé-Kénitra",
            "work_type": "construction",
            "site_partner_id": self.env["res.partner"].create({
                "name": "Other-company site"
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
        chantier = other_env["project.project"].create({
            "name": "Cost chantier",
            "is_chantier": True,
            "company_id": other_company.id,
            "warehouse_id": other_warehouse.id,
            "chantier_region": "Marrakesh-Safi",
            "work_type": "construction",
            "partner_id": other_env["res.partner"].create({
                "name": "Cost customer"
            }).id,
            "date_start": date(2026, 1, 1),
            "date": date(2026, 12, 31),
            "site_partner_id": other_env["res.partner"].create({
                "name": "Cost site"
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
        loss_location = other_env["stock.picking"]._get_chantier_loss_location(
            other_company
        )
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
