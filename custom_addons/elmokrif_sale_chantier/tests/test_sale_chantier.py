from datetime import date

from odoo.exceptions import AccessError, UserError, ValidationError
from odoo.tests import TransactionCase, tagged


@tagged("post_install", "-at_install")
class TestSaleChantier(TransactionCase):
    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.company = cls.env.company
        cls.partner = cls.env["res.partner"].create({
            "name": "Chantier Customer",
            "customer_rank": 1,
        })
        cls.site = cls.env["res.partner"].create({
            "name": "Chantier Site Address",
            "parent_id": cls.partner.id,
            "type": "delivery",
        })
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
        defaults = {
                "name": name,
                "is_chantier": True,
                "company_id": self.company.id,
                "warehouse_id": self.warehouse.id,
                "partner_id": self.partner.id,
                "site_partner_id": self.site.id,
                "chantier_region": "Casablanca-Settat",
                "work_type": "construction",
                "date_start": date(2026, 1, 1),
                "date": date(2026, 12, 31),
        }
        defaults.update(values)
        chantier = self.env["project.project"].with_context(
            default_is_chantier=True
        ).create(defaults)
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
        chantier = self.env["project.project"].with_context(
            default_is_chantier=True
        ).create(
            {
                "name": "Not Initialized",
                "is_chantier": True,
                "company_id": self.company.id,
                "warehouse_id": self.warehouse.id,
                "partner_id": self.partner.id,
                "site_partner_id": self.site.id,
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

    def test_independent_site_address_does_not_replace_chantier_customer(self):
        independent_site = self.env["res.partner"].create({
            "name": "Independent physical site",
            "type": "other",
        })
        chantier = self._create_chantier(site_partner_id=independent_site.id)

        order = self._create_order(chantier)

        self.assertEqual(order.partner_id, chantier.partner_id)
        self.assertEqual(order.chantier_id, chantier)

    def test_ordinary_order_confirms_without_a_chantier(self):
        order = self.env["sale.order"].create({
            "partner_id": self.partner.id,
            "company_id": self.company.id,
            "order_line": [(0, 0, {
                "product_id": self.product.id,
                "product_uom_qty": 1,
            })],
        })

        order.action_confirm()

        self.assertEqual(order.state, "sale")
        self.assertFalse(order.chantier_id)

    def test_customer_selection_does_not_implicitly_declare_a_chantier_order(self):
        self._create_chantier()
        order = self.env["sale.order"].new({
            "partner_id": self.partner.id,
            "company_id": self.company.id,
        })

        order._onchange_partner_chantier()

        self.assertFalse(order.chantier_id)

    def test_chantier_allocation_preserves_another_analytic_dimension(self):
        chantier = self._create_chantier()
        second_plan = self.env["account.analytic.plan"].create({
            "name": "Sales Region",
        })
        region_account = self.env["account.analytic.account"].create({
            "name": "Casablanca Sales",
            "plan_id": second_plan.id,
            "company_id": self.company.id,
        })
        order = self.env["sale.order"].create({
            "partner_id": self.partner.id,
            "company_id": self.company.id,
            "order_line": [(0, 0, {
                "product_id": self.product.id,
                "product_uom_qty": 1,
                "analytic_distribution": {str(region_account.id): 100.0},
            })],
        })

        order.write({"chantier_id": chantier.id})

        distribution = order.order_line.analytic_distribution
        self.assertEqual(distribution[str(region_account.id)], 100.0)
        self.assertEqual(distribution[str(chantier.analytic_account_id.id)], 100.0)

    def test_followup_is_unique_and_closes_on_confirmation(self):
        chantier = self._create_chantier()
        order = self._create_order(chantier)
        order.write({"state": "sent"})

        order._schedule_first_chantier_followup()
        order._schedule_first_chantier_followup()

        activities = self.env["mail.activity"].search([
            ("res_model", "=", "sale.order"),
            ("res_id", "=", order.id),
            ("is_chantier_followup", "=", True),
        ])
        self.assertEqual(len(activities), 1)
        order.action_confirm()
        self.assertFalse(activities.exists())
        self.assertFalse(order.chantier_followup_activity_id)

    def test_salesperson_cannot_create_products(self):
        salesperson = self.env["res.users"].with_context(no_reset_password=True).create({
            "name": "UAT sales role",
            "login": "uat_sales_role_test",
            "groups_id": [(6, 0, [
                self.env.ref("base.group_user").id,
                self.env.ref("sales_team.group_sale_salesman").id,
                self.env.ref("elmokrif_chantier.group_chantier_sales_reader").id,
            ])],
        })

        with self.assertRaises(AccessError):
            self.env["product.template"].with_user(salesperson).create({
                "name": "Unauthorized product",
            })
