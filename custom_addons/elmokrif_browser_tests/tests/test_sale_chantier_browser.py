from datetime import date, timedelta

from odoo import Command, fields
from odoo.tests import HttpCase, tagged


@tagged("post_install", "-at_install", "elmokrif_browser")
class TestSaleChantierBrowser(HttpCase):
    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.company = cls.env.company
        cls.company.sale_chantier_followup_delay_days = 3
        cls.customer = cls.env["res.partner"].create({
            "name": "Browser Acceptance Customer",
            "email": "browser.customer@example.test",
            "customer_rank": 1,
        })
        cls.site = cls.env["res.partner"].create({
            "name": "Browser Acceptance Site",
            "parent_id": cls.customer.id,
            "type": "delivery",
        })
        cls.salesperson = cls._create_user(
            "Browser Chantier Salesperson",
            "browser_chantier_salesperson",
            [
                "sales_team.group_sale_salesman",
                "elmokrif_chantier.group_chantier_user",
            ],
        )
        cls.accountant = cls._create_user(
            "Browser Chantier Accountant",
            "browser_chantier_accountant",
            [
                "account.group_account_invoice",
                "elmokrif_chantier.group_chantier_user",
            ],
        )
        cls.warehouse = cls.env["stock.warehouse"].search(
            [("company_id", "=", cls.company.id)], limit=1
        )
        cls.chantier_a = cls._create_chantier("Browser Site A")
        cls.chantier_b = cls._create_chantier("Browser Site B")
        cls.product_a = cls.env["product.product"].create({
            "name": "Browser Acceptance Service A",
            "type": "service",
            "list_price": 5000,
        })
        cls.product_b = cls.env["product.product"].create({
            "name": "Browser Acceptance Service B",
            "type": "service",
            "list_price": 7000,
        })
        cls.order = cls.env["sale.order"].create({
            "partner_id": cls.customer.id,
            "company_id": cls.company.id,
            "user_id": cls.salesperson.id,
            "chantier_id": cls.chantier_a.id,
            "order_line": [
                Command.create({
                    "product_id": cls.product_a.id,
                    "product_uom_qty": 1,
                    "chantier_id": cls.chantier_a.id,
                }),
                Command.create({
                    "product_id": cls.product_b.id,
                    "product_uom_qty": 1,
                    "chantier_id": cls.chantier_b.id,
                }),
            ],
        })

    @classmethod
    def _create_user(cls, name, login, groups):
        return cls.env["res.users"].with_context(no_reset_password=True).create({
            "name": name,
            "login": login,
            "email": "%s@example.test" % login,
            "password": login,
            "company_id": cls.company.id,
            "company_ids": [Command.set([cls.company.id])],
            "groups_id": [Command.set([
                cls.env.ref("base.group_user").id,
                *[cls.env.ref(xmlid).id for xmlid in groups],
            ])],
        })

    @classmethod
    def _create_chantier(cls, name):
        chantier = cls.env["project.project"].with_context(
            default_is_chantier=True
        ).create({
            "name": name,
            "is_chantier": True,
            "company_id": cls.company.id,
            "warehouse_id": cls.warehouse.id,
            "partner_id": cls.customer.id,
            "site_partner_id": cls.site.id,
            "user_id": cls.env.user.id,
            "chantier_member_ids": [Command.set([
                cls.salesperson.id,
                cls.accountant.id,
            ])],
            "chantier_region": "Casablanca-Settat",
            "work_type": "construction",
            "date_start": date(2026, 1, 1),
            "date": date(2026, 12, 31),
        })
        chantier.action_approve_chantier()
        chantier.action_initialize_chantier()
        chantier.action_start_chantier()
        return chantier

    def _form_url(self, model, record):
        return "/web#id=%s&model=%s&view_type=form" % (record.id, model)

    def test_salesperson_send_followup_confirm_and_accountant_invoice(self):
        self.start_tour(
            self._form_url("sale.order", self.order),
            "elmokrif_sale_chantier_send",
            login=self.salesperson.login,
            timeout=120,
        )
        self.order.invalidate_recordset()
        self.assertEqual(self.order.state, "sent")
        self.assertTrue(self.order.chantier_first_sent_at)
        self.assertEqual(
            self.order.chantier_followup_activity_id.date_deadline,
            fields.Date.today() + timedelta(days=3),
        )

        self.start_tour(
            self._form_url("sale.order", self.order),
            "elmokrif_sale_chantier_confirm",
            login=self.salesperson.login,
            timeout=120,
        )
        self.order.invalidate_recordset()
        self.assertEqual(self.order.state, "sale")
        self.assertFalse(self.order.chantier_followup_activity_id)

        invoice = self.order._create_invoices()
        allocated_lines = invoice.invoice_line_ids.filtered("sale_line_id")
        self.assertEqual(
            set(allocated_lines.mapped("chantier_id").ids),
            {self.chantier_a.id, self.chantier_b.id},
        )
        self.start_tour(
            self._form_url("account.move", invoice),
            "elmokrif_sale_chantier_invoice",
            login=self.accountant.login,
            timeout=120,
        )
        invoice.invalidate_recordset()
        self.assertEqual(invoice.state, "posted")
