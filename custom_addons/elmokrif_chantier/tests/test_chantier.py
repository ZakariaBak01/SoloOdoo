from datetime import date, timedelta

from odoo.exceptions import AccessError, UserError, ValidationError
from odoo.tests import TransactionCase, tagged
from odoo.tools.safe_eval import safe_eval


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
        if "partner_id" not in values:
            values["partner_id"] = self.env["res.partner"].create({
                "name": "Test Customer",
                "customer_rank": 1,
            }).id
        values.setdefault("user_id", self.env.user.id)
        values.setdefault("date_start", date(2026, 1, 1))
        values.setdefault("date", date(2026, 12, 31))
        values.setdefault("chantier_region", "Casablanca-Settat")
        values.setdefault("work_type", "construction")
        if "site_partner_id" not in values:
            values["site_partner_id"] = self.env["res.partner"].create({
                "name": "Test Site Address",
                "type": "other",
            }).id
        return self.env["project.project"].create(values)

    def test_site_address_accepts_only_address_records(self):
        contact = self.env["res.partner"].create({
            "name": "Not a Site Address",
            "type": "contact",
        })
        with self.assertRaisesRegex(ValidationError, "Site Address must be"):
            self._create_chantier(site_partner_id=contact.id)

        for address_type in ("delivery", "other"):
            site = self.env["res.partner"].create({
                "name": f"{address_type.title()} Site Address",
                "type": address_type,
            })
            chantier = self._create_chantier(site_partner_id=site.id)
            self.assertEqual(chantier.site_partner_id, site)

    def test_chantier_accepts_only_registered_customers(self):
        for invalid_partner in (
            self.env.user.partner_id,
            self.env.company.partner_id,
            self.env["res.partner"].create({
                "name": "Supplier-only Contact",
                "supplier_rank": 1,
            }),
        ):
            with self.assertRaisesRegex(ValidationError, "registered customer"):
                self._create_chantier(partner_id=invalid_partner.id)

        customer = self.env["res.partner"].create({
            "name": "Registered Customer",
            "customer_rank": 1,
        })
        chantier = self._create_chantier(partner_id=customer.id)
        self.assertEqual(chantier.partner_id, customer)

    def test_inline_customer_defaults_to_registered_customer(self):
        customer = self.env["res.partner"].with_context(
            default_customer_rank=1,
            default_company_type="company",
        ).create({"name": "Inline Customer"})

        self.assertGreater(customer.customer_rank, 0)
        self.assertTrue(customer.is_company)

    def test_chantier_manager_can_create_site_addresses(self):
        manager = self.env["res.users"].with_context(no_reset_password=True).create({
            "name": "Site address manager",
            "login": "site_address_manager@example.test",
            "groups_id": [(6, 0, [
                self.env.ref("base.group_user").id,
                self.env.ref("elmokrif_chantier.group_chantier_manager").id,
            ])],
        })

        self.assertTrue(manager.has_group("base.group_partner_manager"))
        site = self.env["res.partner"].with_user(manager).create({
            "name": "Manager-created Site Address",
            "type": "other",
        })
        self.assertEqual(site.type, "other")

    def test_site_address_uses_dedicated_creation_form(self):
        site_form = self.env.ref("elmokrif_chantier.view_chantier_site_partner_form")
        self.assertEqual(site_form.model, "res.partner")
        self.assertIn('string="Site Name"', site_form.arch_db)
        self.assertIn('string="Physical Address"', site_form.arch_db)
        self.assertNotIn('name="company_type"', site_form.arch_db)
        self.assertNotIn('name="function"', site_form.arch_db)

        chantier_form = self.env.ref(
            "elmokrif_chantier.project_project_form_chantier"
        )
        self.assertIn(
            "elmokrif_chantier.view_chantier_site_partner_form",
            chantier_form.arch_db,
        )

    def test_customer_uses_dedicated_creation_form(self):
        customer_form = self.env.ref(
            "elmokrif_chantier.view_chantier_customer_partner_form"
        )
        self.assertEqual(customer_form.model, "res.partner")
        self.assertIn('string="Customer Name"', customer_form.arch_db)
        self.assertIn('string="Primary Address"', customer_form.arch_db)
        self.assertNotIn('name="function"', customer_form.arch_db)

        chantier_form = self.env.ref(
            "elmokrif_chantier.project_project_form_chantier"
        )
        self.assertIn("customer_rank", chantier_form.arch_db)
        self.assertIn(
            "elmokrif_chantier.view_chantier_customer_partner_form",
            chantier_form.arch_db,
        )

    def test_chantier_team_candidates_are_role_and_company_scoped(self):
        manager = self.env["res.users"].with_context(no_reset_password=True).create({
            "name": "Eligible chantier manager",
            "login": "eligible_chantier_manager@example.test",
            "company_id": self.company.id,
            "company_ids": [(6, 0, [self.company.id])],
            "groups_id": [(6, 0, [
                self.env.ref("base.group_user").id,
                self.env.ref("elmokrif_chantier.group_chantier_manager").id,
            ])],
        })
        member = self.env["res.users"].with_context(no_reset_password=True).create({
            "name": "Eligible chantier member",
            "login": "eligible_chantier_member@example.test",
            "company_id": self.company.id,
            "company_ids": [(6, 0, [self.company.id])],
            "groups_id": [(6, 0, [
                self.env.ref("base.group_user").id,
                self.env.ref("elmokrif_chantier.group_chantier_user").id,
            ])],
        })
        unrelated = self.env["res.users"].with_context(no_reset_password=True).create({
            "name": "Unrelated internal user",
            "login": "unrelated_internal_user@example.test",
            "company_id": self.company.id,
            "company_ids": [(6, 0, [self.company.id])],
            "groups_id": [(6, 0, [self.env.ref("base.group_user").id])],
        })
        other_company = self.env["res.company"].create({"name": "Other company"})
        other_company_member = self.env["res.users"].with_context(
            no_reset_password=True
        ).create({
            "name": "Other-company chantier member",
            "login": "other_company_chantier_member@example.test",
            "company_id": other_company.id,
            "company_ids": [(6, 0, [other_company.id])],
            "groups_id": [(6, 0, [
                self.env.ref("base.group_user").id,
                self.env.ref("elmokrif_chantier.group_chantier_user").id,
            ])],
        })

        chantier = self._create_chantier(
            user_id=manager.id,
            chantier_member_ids=[(6, 0, [member.id])],
        )

        self.assertIn(manager, chantier.eligible_chantier_manager_ids)
        self.assertNotIn(member, chantier.eligible_chantier_manager_ids)
        self.assertIn(member, chantier.eligible_chantier_member_ids)
        self.assertNotIn(unrelated, chantier.eligible_chantier_member_ids)
        self.assertNotIn(other_company_member, chantier.eligible_chantier_member_ids)

        with self.assertRaisesRegex(ValidationError, "lack the Chantier User role"):
            chantier.write({"chantier_member_ids": [(4, unrelated.id)]})

    def test_chantier_manager_must_have_manager_role_and_company_access(self):
        chantier_user = self.env["res.users"].with_context(
            no_reset_password=True
        ).create({
            "name": "Non-manager chantier user",
            "login": "non_manager_chantier_user@example.test",
            "company_id": self.company.id,
            "company_ids": [(6, 0, [self.company.id])],
            "groups_id": [(6, 0, [
                self.env.ref("base.group_user").id,
                self.env.ref("elmokrif_chantier.group_chantier_user").id,
            ])],
        })

        with self.assertRaisesRegex(ValidationError, "Chantier Manager must be"):
            self._create_chantier(user_id=chantier_user.id)

    def test_chantier_hides_inbound_email_alias_settings(self):
        chantier_form = self.env.ref(
            "elmokrif_chantier.project_project_form_chantier"
        )

        self.assertIn("//page[@name='settings']//div[@name='alias_def']", chantier_form.arch_db)
        self.assertIn("//page[@name='settings']//field[@name='alias_contact']", chantier_form.arch_db)

    def test_chantier_manager_can_review_generated_analytic_links(self):
        chantier_form = self.env.ref(
            "elmokrif_chantier.project_project_form_chantier"
        )

        self.assertIn(
            'groups="elmokrif_chantier.group_chantier_manager"',
            chantier_form.arch_db,
        )
        self.assertNotIn(
            'groups="analytic.group_analytic_accounting"',
            chantier_form.arch_db,
        )
        self.assertEqual(
            chantier_form.arch_db.count("'no_open': True"),
            2,
        )

    def test_initialization_does_not_require_sender_email(self):
        manager = self.env["res.users"].with_context(no_reset_password=True).create({
            "name": "Manager without email",
            "login": "manager_without_email",
            "email": False,
            "company_id": self.company.id,
            "company_ids": [(6, 0, [self.company.id])],
            "groups_id": [(6, 0, [
                self.env.ref("base.group_user").id,
                self.env.ref("elmokrif_chantier.group_chantier_manager").id,
            ])],
        })
        chantier = self._create_chantier(user_id=manager.id)

        chantier.with_user(manager).action_approve_chantier()

        self.assertTrue(chantier.chantier_initialized)
        self.assertTrue(any(
            "Chantier initialized" in str(message.body)
            for message in chantier.message_ids
        ))

    def _approve(self, chantier):
        chantier.action_approve_chantier()

    def test_new_chantier_actions_open_in_edit_mode(self):
        for xmlid in (
            "elmokrif_chantier.action_chantier",
            "elmokrif_chantier.action_new_chantier",
        ):
            context = safe_eval(self.env.ref(xmlid).context)
            self.assertTrue(context["default_is_chantier"])
            self.assertEqual(context["form_view_initial_mode"], "edit")

    def test_new_chantier_defaults_manager_editability(self):
        manager = self.env["res.users"].with_context(no_reset_password=True).create(
            {
                "name": "Chantier form manager",
                "login": "chantier_form_manager@example.test",
                "groups_id": [
                    (6, 0, [
                        self.env.ref("base.group_user").id,
                        self.env.ref("elmokrif_chantier.group_chantier_manager").id,
                    ]),
                ],
            }
        )

        defaults = self.env["project.project"].with_user(manager).default_get(
            ["can_manage_chantier"]
        )

        self.assertTrue(defaults["can_manage_chantier"])

    def test_new_chantier_defaults_active_company_for_warehouse_domain(self):
        defaults = self.env["project.project"].with_context(
            default_is_chantier=True
        ).default_get(["company_id", "warehouse_id"])

        self.assertEqual(defaults["company_id"], self.env.company.id)

    def test_public_context_cannot_replace_system_links(self):
        chantier = self._create_chantier()
        self._approve(chantier)
        chantier.action_initialize_chantier()
        other_location = self.env["stock.location"].create({
            "name": "Forged Site",
            "usage": "internal",
            "location_id": self.warehouse.view_location_id.id,
            "company_id": self.company.id,
        })
        with self.assertRaises(UserError):
            chantier.with_context(chantier_initialization=True).write({
                "site_location_id": other_location.id
            })

    def test_initialize_is_idempotent(self):
        chantier = self._create_chantier()

        self._approve(chantier)
        chantier.action_initialize_chantier()
        analytic_account = chantier.analytic_account_id
        site_location = chantier.site_location_id

        chantier.action_initialize_chantier()

        self.assertEqual(chantier.analytic_account_id, analytic_account)
        self.assertEqual(
            analytic_account.plan_id,
            self.env.ref("elmokrif_chantier.analytic_plan_chantier"),
        )
        self.assertEqual(analytic_account.chantier_id, chantier)
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

    def test_task_work_type_is_limited_to_chantiers(self):
        chantier = self._create_chantier()
        task = self.env["project.task"].create({
            "name": "Chantier work package",
            "project_id": chantier.id,
            "chantier_work_type": "carpentry",
            "chantier_bundle": "Carpentry package",
            "date_deadline": date(2026, 6, 1),
        })
        self.assertEqual(task.chantier_work_type, "carpentry")

        ordinary_project = self.env["project.project"].create({
            "name": "Ordinary project",
        })
        with self.assertRaises(ValidationError):
            self.env["project.task"].create({
                "name": "Ordinary task",
                "project_id": ordinary_project.id,
                "chantier_work_type": "carpentry",
            })

    def test_invalid_lifecycle_jump_is_rejected(self):
        chantier = self._create_chantier()

        with self.assertRaises(UserError):
            chantier.action_start_chantier()

    def test_approval_requires_master_data(self):
        required_fields = (
            "partner_id",
            "user_id",
            "date_start",
            "date",
            "chantier_region",
            "work_type",
            "site_partner_id",
            "warehouse_id",
        )
        for field_name in required_fields:
            with self.subTest(field=field_name):
                chantier = self._create_chantier(**{field_name: False})
                with self.assertRaises(UserError):
                    chantier.action_approve_chantier()

    def test_approval_initializes_analytic_account_and_site_location(self):
        chantier = self._create_chantier()

        chantier.action_approve_chantier()

        self.assertEqual(chantier.chantier_state, "approved")
        self.assertTrue(chantier.chantier_initialized)
        self.assertEqual(
            chantier.analytic_account_id.plan_id,
            self.env.ref("elmokrif_chantier.analytic_plan_chantier"),
        )
        self.assertEqual(chantier.analytic_account_id.chantier_id, chantier)
        self.assertEqual(chantier.site_location_id.chantier_id, chantier)
        self.assertTrue(any(
            "Chantier initialized" in str(message.body)
            for message in chantier.message_ids
        ))

    def test_start_repairs_approved_chantier_missing_system_links(self):
        chantier = self._create_chantier()
        self.env.cr.execute(
            "UPDATE project_project SET chantier_state = 'approved' WHERE id = %s",
            [chantier.id],
        )
        chantier.invalidate_recordset(
            ["chantier_state", "analytic_account_id", "site_location_id"]
        )

        chantier.action_start_chantier()

        self.assertEqual(chantier.chantier_state, "in_progress")
        self.assertTrue(chantier.chantier_initialized)

    def test_initialization_adopts_a_companyless_legacy_analytic_account(self):
        chantier = self._create_chantier()
        analytic_account = self.env["account.analytic.account"].create({
            "name": "Legacy companyless analytic account",
            "plan_id": self.env.ref(
                "elmokrif_chantier.analytic_plan_chantier"
            ).id,
        })
        # Simulate a chantier created before reciprocal ownership and company
        # scoping were introduced.
        self.env.cr.execute(
            """
            UPDATE project_project
               SET chantier_state = 'approved', analytic_account_id = %s
             WHERE id = %s
            """,
            [analytic_account.id, chantier.id],
        )
        chantier.invalidate_recordset(
            ["chantier_state", "analytic_account_id", "site_location_id"]
        )
        analytic_account.invalidate_recordset(["company_id", "chantier_id"])

        chantier.action_initialize_chantier()

        self.assertEqual(analytic_account.company_id, chantier.company_id)
        self.assertEqual(analytic_account.chantier_id, chantier)
        self.assertTrue(chantier.chantier_initialized)

    def test_initialization_requires_approval(self):
        chantier = self._create_chantier()

        with self.assertRaises(UserError):
            chantier.action_initialize_chantier()

    def test_initialized_location_cannot_be_replaced_manually(self):
        chantier = self._create_chantier()
        self._approve(chantier)
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

    def test_site_location_is_outside_warehouse_stock_subtree(self):
        chantier = self._create_chantier()
        self._approve(chantier)
        chantier.action_initialize_chantier()

        self.assertEqual(chantier.site_location_id.location_id, self.warehouse.view_location_id)
        self.assertFalse(
            chantier.site_location_id.id
            in self.env["stock.location"].search([
                ("id", "child_of", self.warehouse.lot_stock_id.id)
            ]).ids
        )

    def test_site_stock_cannot_reserve_a_warehouse_delivery_for_another_chantier(self):
        site_a = self._create_chantier(name="Site A")
        site_b = self._create_chantier(name="Site B")
        for chantier in (site_a, site_b):
            self._approve(chantier)
            chantier.action_initialize_chantier()
        product = self.env["product.product"].create(
            {"name": "Isolated stock", "type": "product"}
        )
        self.env["stock.quant"]._update_available_quantity(
            product, site_a.site_location_id, 10
        )
        picking = self.env["stock.picking"].create({
            "picking_type_id": self.warehouse.int_type_id.id,
            "location_id": self.warehouse.lot_stock_id.id,
            "location_dest_id": site_b.site_location_id.id,
            "move_ids_without_package": [(0, 0, {
                "name": product.display_name,
                "product_id": product.id,
                "product_uom_qty": 10,
                "product_uom": product.uom_id.id,
                "location_id": self.warehouse.lot_stock_id.id,
                "location_dest_id": site_b.site_location_id.id,
            })],
        })
        picking.action_confirm()
        picking.action_assign()

        self.assertEqual(picking.move_ids.quantity, 0)

    def test_legacy_location_migration_reassigns_invalid_reservations(self):
        site_a = self._create_chantier(name="Legacy Site A")
        site_b = self._create_chantier(name="Legacy Site B")
        for chantier in (site_a, site_b):
            self._approve(chantier)
            chantier.action_initialize_chantier()
        # Reproduce the pre-fix hierarchy and the reservation it allowed.
        site_a.site_location_id.sudo().write({
            "location_id": self.warehouse.lot_stock_id.id,
        })
        product = self.env["product.product"].create(
            {"name": "Legacy isolated stock", "type": "product"}
        )
        self.env["stock.quant"]._update_available_quantity(
            product, site_a.site_location_id, 10
        )
        picking = self.env["stock.picking"].create({
            "picking_type_id": self.warehouse.int_type_id.id,
            "location_id": self.warehouse.lot_stock_id.id,
            "location_dest_id": site_b.site_location_id.id,
            "move_ids_without_package": [(0, 0, {
                "name": product.display_name,
                "product_id": product.id,
                "product_uom_qty": 10,
                "product_uom": product.uom_id.id,
                "location_id": self.warehouse.lot_stock_id.id,
                "location_dest_id": site_b.site_location_id.id,
            })],
        })
        picking.action_confirm()
        picking.action_assign()
        self.assertEqual(picking.move_ids.quantity, 10)

        site_a.sudo()._relocate_legacy_site_locations()

        self.assertEqual(site_a.site_location_id.location_id, self.warehouse.view_location_id)
        picking.move_ids.invalidate_recordset(["quantity"])
        self.assertEqual(picking.move_ids.quantity, 0)

    def test_direct_approval_and_start_writes_enforce_workflow(self):
        incomplete = self._create_chantier(chantier_region=False)
        with self.assertRaises(UserError):
            incomplete.sudo().write({"chantier_state": "approved"})

        with self.assertRaises(UserError):
            self._create_chantier(chantier_state="in_progress")

        with self.assertRaises(UserError):
            self.env["project.project"].with_context(
                default_is_chantier=True,
                default_chantier_state="approved",
            ).create({"name": "Context-approved chantier"})

    def test_create_rejects_manual_system_links(self):
        analytic_account = self.env["account.analytic.account"].create({
            "name": "Manual Chantier Account",
            "plan_id": self.env.ref(
                "elmokrif_chantier.analytic_plan_chantier"
            ).id,
            "company_id": self.company.id,
        })

        with self.assertRaises(UserError):
            self._create_chantier(analytic_account_id=analytic_account.id)

    def test_new_chantier_form_ignores_hidden_system_link_values(self):
        analytic_account = self.env["account.analytic.account"].create({
            "name": "Hidden Form Account",
            "plan_id": self.env.ref(
                "elmokrif_chantier.analytic_plan_chantier"
            ).id,
            "company_id": self.company.id,
        })

        chantier = self.env["project.project"].with_context(
            default_is_chantier=True
        ).create({
            "name": "New Form Chantier",
            "is_chantier": True,
            "company_id": self.company.id,
            "warehouse_id": self.warehouse.id,
            "partner_id": self.env["res.partner"].create({
                "name": "New Form Customer",
                "customer_rank": 1,
            }).id,
            "user_id": self.env.user.id,
            "date_start": date(2026, 1, 1),
            "date": date(2026, 12, 31),
            "chantier_region": "Casablanca-Settat",
            "work_type": "construction",
            "site_partner_id": self.env["res.partner"].create({
                "name": "New Form Site",
                "type": "other",
            }).id,
            "analytic_account_id": analytic_account.id,
        })

        self.assertEqual(chantier.analytic_account_id, analytic_account)
        self.assertEqual(
            chantier.analytic_account_id.plan_id,
            self.env.ref("elmokrif_chantier.analytic_plan_chantier"),
        )
        self.assertEqual(chantier.analytic_account_id.chantier_id, chantier)
        chantier.action_approve_chantier()
        self.assertTrue(chantier.chantier_initialized)

    def test_new_chantier_cannot_take_an_analytic_account_in_use(self):
        existing = self.env["project.project"].create({"name": "Existing project"})
        analytic_account = self.env["account.analytic.account"].create({
            "name": "Existing Project Account",
            "plan_id": self.env.ref("elmokrif_chantier.analytic_plan_chantier").id,
            "company_id": self.company.id,
        })
        existing.write({"analytic_account_id": analytic_account.id})

        with self.assertRaises(UserError):
            self.env["project.project"].with_context(
                default_is_chantier=True,
                default_analytic_account_id=analytic_account.id,
            ).create({"name": "Analytic account hijack"})

    def test_context_defaults_cannot_create_foundation_links(self):
        chantier = self._create_chantier()
        with self.assertRaises(UserError):
            self.env["account.analytic.account"].with_context(
                default_chantier_id=chantier.id
            ).create({
                "name": "Forged linked account",
                "plan_id": self.env.ref("elmokrif_chantier.analytic_plan_chantier").id,
                "company_id": self.company.id,
            })
        with self.assertRaises(UserError):
            self.env["stock.location"].with_context(
                default_chantier_id=chantier.id
            ).create({
                "name": "Forged linked location",
                "usage": "internal",
                "location_id": self.warehouse.view_location_id.id,
                "company_id": self.company.id,
            })

    def test_chantiers_are_archived_instead_of_deleted(self):
        draft = self._create_chantier(name="Draft chantier")
        with self.assertRaises(UserError):
            draft.unlink()
        with self.assertRaises(UserError):
            draft.write({"active": False})

        chantier = self._create_chantier(name="Archived chantier")
        self._approve(chantier)
        chantier.action_start_chantier()
        chantier.action_complete_chantier()
        chantier.action_close_chantier()
        chantier.action_archive_chantier()

        self.assertFalse(chantier.active)

    def test_reopening_requires_fresh_reason_and_keeps_audit_message(self):
        chantier = self._create_chantier()
        self._approve(chantier)
        chantier.action_start_chantier()
        chantier.action_complete_chantier()
        chantier.action_close_chantier()
        chantier.action_archive_chantier()

        self.assertFalse(chantier.active)

        with self.assertRaises(ValidationError):
            chantier.action_reopen_chantier()

        chantier.reopen_reason = "Customer requested corrective work"
        chantier.action_reopen_chantier()

        self.assertEqual(chantier.chantier_state, "approved")
        self.assertTrue(chantier.active)
        self.assertFalse(chantier.reopen_reason)
        self.assertTrue(any(
            "Customer requested corrective work" in str(message.body)
            for message in chantier.message_ids
        ))

    def test_assigned_chantier_user_can_run_operational_lifecycle(self):
        user = self.env["res.users"].with_context(no_reset_password=True).create({
            "name": "Assigned chantier user",
            "login": "assigned_chantier_user",
            "email": "assigned_chantier_user@example.test",
            "groups_id": [(6, 0, [
                self.env.ref("base.group_user").id,
                self.env.ref("elmokrif_chantier.group_chantier_user").id,
            ])],
        })
        chantier = self._create_chantier(
            chantier_member_ids=[(6, 0, [user.id])],
            privacy_visibility="followers",
        )
        self._approve(chantier)

        self.assertIn(user.partner_id, chantier.message_partner_ids)
        self.assertEqual(chantier.last_update_status, "at_risk")
        chantier.with_user(user).action_start_chantier()
        self.assertEqual(chantier.last_update_status, "at_risk")
        chantier.with_user(user).action_hold_chantier()
        self.assertEqual(chantier.last_update_status, "on_hold")
        chantier.with_user(user).action_start_chantier()
        self.assertEqual(chantier.last_update_status, "at_risk")
        chantier.with_user(user).action_complete_chantier()

        self.assertEqual(chantier.chantier_state, "completed")
        self.assertEqual(chantier.last_update_status, "done")

    def test_health_checker_uses_schedule_and_task_evidence(self):
        today = date.today()
        chantier = self._create_chantier(
            date_start=today - timedelta(days=10),
            date=today + timedelta(days=10),
        )
        self._approve(chantier)
        chantier.action_start_chantier()
        self.assertEqual(chantier.last_update_status, "at_risk")
        self.assertIn("No active tasks", chantier.health_check_reason)

        task = self.env["project.task"].create({
            "name": "Late construction task",
            "project_id": chantier.id,
            "date_deadline": today - timedelta(days=1),
            "chantier_bundle": "Construction package",
            "priority": "1",
        })
        self.assertEqual(chantier.last_update_status, "off_track")
        self.assertIn("past their deadline", chantier.health_check_reason)

        task.write({"date_deadline": today + timedelta(days=5)})
        self.assertEqual(chantier.last_update_status, "at_risk")
        self.assertIn("Task completion", chantier.health_check_reason)

        chantier.action_hold_chantier()
        self.assertEqual(chantier.last_update_status, "on_hold")
        chantier.action_complete_chantier()
        self.assertEqual(chantier.last_update_status, "done")

    def test_chantier_user_cannot_access_unassigned_chantier_or_edit_project(self):
        user = self.env["res.users"].with_context(no_reset_password=True).create({
            "name": "Restricted chantier user",
            "login": "restricted_chantier_user",
            "email": "restricted_chantier_user@example.test",
            "groups_id": [(6, 0, [
                self.env.ref("base.group_user").id,
                self.env.ref("elmokrif_chantier.group_chantier_user").id,
            ])],
        })
        chantier = self._create_chantier(name="Unassigned chantier")
        ordinary_project = self.env["project.project"].create({
            "name": "Ordinary project",
        })

        self.assertFalse(
            self.env["project.project"].with_user(user).search([
                ("id", "=", chantier.id),
            ])
        )
        with self.assertRaises(AccessError):
            ordinary_project.with_user(user).write({"name": "Forbidden edit"})

        self.assertFalse(
            self.env["stock.location"].with_user(user).search([
                ("id", "=", chantier.site_location_id.id),
            ])
        )

    def test_storekeeper_can_access_unassigned_chantier_location(self):
        storekeeper = self.env["res.users"].with_context(no_reset_password=True).create({
            "name": "Chantier stock storekeeper",
            "login": "chantier_stock_storekeeper",
            "email": "chantier_stock_storekeeper@example.test",
            "groups_id": [(6, 0, [
                self.env.ref("base.group_user").id,
                self.env.ref("stock.group_stock_user").id,
            ])],
        })
        chantier = self._create_chantier(name="Storekeeper destination chantier")
        self._approve(chantier)

        location = self.env["stock.location"].with_user(storekeeper).search([
            ("id", "=", chantier.site_location_id.id),
        ])

        self.assertEqual(location, chantier.site_location_id)

    def test_sales_contact_can_read_only_their_quotation_chantier_reference(self):
        salesperson = self.env["res.users"].with_context(no_reset_password=True).create({
            "name": "Chantier sales reference user",
            "login": "chantier_sales_reference_user",
            "email": "chantier_sales_reference_user@example.test",
            "groups_id": [(6, 0, [
                self.env.ref("base.group_user").id,
                self.env.ref("elmokrif_chantier.group_chantier_sales_reader").id,
            ])],
        })
        accessible = self._create_chantier(
            name="Sales quotation chantier",
            sales_user_ids=[(6, 0, [salesperson.id])],
        )
        restricted = self._create_chantier(name="Restricted commercial chantier")

        visible = self.env["project.project"].with_user(salesperson).search([
            ("id", "in", [accessible.id, restricted.id]),
        ])
        self.assertEqual(visible, accessible)
        visible_analytic_accounts = self.env[
            "account.analytic.account"
        ].with_user(salesperson).search([
            ("id", "in", [
                accessible.analytic_account_id.id,
                restricted.analytic_account_id.id,
            ]),
        ])
        self.assertEqual(
            visible_analytic_accounts,
            accessible.analytic_account_id,
        )
        with self.assertRaises(AccessError):
            accessible.with_user(salesperson).write({"name": "Forbidden commercial edit"})

    def test_open_tasks_block_closure(self):
        chantier = self._create_chantier()
        self._approve(chantier)
        chantier.action_start_chantier()
        chantier.action_complete_chantier()
        self.env["project.task"].create({
            "name": "Incomplete work package",
            "project_id": chantier.id,
            "chantier_bundle": "Closure package",
            "date_deadline": date.today() + timedelta(days=1),
        })

        with self.assertRaises(UserError):
            chantier.action_close_chantier()

    def test_direct_close_write_checks_remaining_stock(self):
        chantier = self._create_chantier()
        self._approve(chantier)
        chantier.action_initialize_chantier()
        chantier.action_start_chantier()
        chantier.action_complete_chantier()
        product = self.env["product.product"].create(
            {"name": "Closure stock", "type": "product"}
        )
        self.env["stock.quant"]._update_available_quantity(
            product, chantier.site_location_id, 1
        )

        with self.assertRaises(UserError):
            chantier.sudo().write({"chantier_state": "closed"})

    def test_chantier_manager_can_initialize_without_inventory_administrator(self):
        manager = self.env["res.users"].with_context(no_reset_password=True).create({
            "name": "Chantier manager",
            "login": "chantier_manager",
            "email": "chantier_manager@example.test",
            "groups_id": [(6, 0, [
                self.env.ref("base.group_user").id,
                self.env.ref("elmokrif_chantier.group_chantier_manager").id,
            ])],
        })
        chantier = self._create_chantier(user_id=manager.id)

        chantier.with_user(manager).action_approve_chantier()
        chantier.with_user(manager).action_initialize_chantier()

        self.assertTrue(chantier.site_location_id)
        self.assertFalse(
            manager.with_user(manager).has_group("stock.group_stock_manager")
        )
