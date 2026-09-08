from datetime import date
from unittest.mock import patch

from odoo import Command
from odoo.exceptions import AccessError, UserError
from odoo.tests import TransactionCase, tagged


@tagged("post_install", "-at_install")
class TestFinanceReadiness(TransactionCase):
    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.company = cls.env.company
        cls.readiness = cls.env["chantier.finance.readiness"].search([
            ("company_id", "=", cls.company.id)
        ], limit=1)
        if not cls.readiness:
            raise AssertionError("The company finance-readiness record was not initialized.")
        cls.manager = cls._create_user(
            "Finance Readiness Manager",
            "finance_readiness_manager@example.test",
            [
                "account.group_account_manager",
                "elmokrif_chantier.group_chantier_user",
            ],
        )
        cls.preparer = cls._create_user(
            "Finance Readiness Preparer",
            "finance_readiness_preparer@example.test",
            [
                "account.group_account_invoice",
                "elmokrif_chantier.group_chantier_user",
            ],
        )
        cls.customer = cls.env["res.partner"].create({"name": "Finance Gate Customer"})
        cls.warehouse = cls.env["stock.warehouse"].search([
            ("company_id", "=", cls.company.id)
        ], limit=1)
        cls.chantier = cls.env["project.project"].with_context(
            default_is_chantier=True
        ).create({
            "name": "Finance Gate Chantier",
            "is_chantier": True,
            "company_id": cls.company.id,
            "warehouse_id": cls.warehouse.id,
            "partner_id": cls.customer.id,
            "site_partner_id": cls.customer.id,
            "user_id": cls.manager.id,
            "favorite_user_ids": [Command.set([cls.manager.id, cls.preparer.id])],
            "chantier_region": "Casablanca-Settat",
            "work_type": "construction",
            "date_start": date(2026, 1, 1),
            "date": date(2026, 12, 31),
        })
        cls.chantier.action_approve_chantier()
        cls.chantier.action_initialize_chantier()
        cls.chantier.action_start_chantier()
        cls.service = cls.env["product.product"].create({
            "name": "Finance Gate Service",
            "type": "service",
            "list_price": 1000,
        })

    @classmethod
    def _create_user(cls, name, login, groups):
        return cls.env["res.users"].with_context(no_reset_password=True).create({
            "name": name,
            "login": login,
            "email": login,
            "company_id": cls.company.id,
            "company_ids": [Command.set([cls.company.id])],
            "groups_id": [Command.set([
                cls.env.ref("base.group_user").id,
                *[cls.env.ref(xmlid).id for xmlid in groups],
            ])],
        })

    def _complete_checklist(self):
        return {
            **{field_name: True for field_name in self.readiness._checklist_fields()},
            "review_notes": "Reviewed against the accountant acceptance evidence.",
        }

    def _draft_invoice(self):
        order = self.env["sale.order"].create({
            "partner_id": self.customer.id,
            "company_id": self.company.id,
            "chantier_id": self.chantier.id,
            "order_line": [Command.create({
                "product_id": self.service.id,
                "product_uom_qty": 1,
                "chantier_id": self.chantier.id,
            })],
        })
        order.action_confirm()
        return order._create_invoices()

    def test_only_accounting_manager_can_approve_complete_checklist(self):
        self.readiness.with_user(self.manager).write(self._complete_checklist())
        with patch.object(type(self.readiness), "_get_technical_errors", return_value=[]):
            with self.assertRaises(AccessError):
                self.readiness.with_user(self.preparer).action_approve()
            self.readiness.with_user(self.manager).action_approve()
        self.assertEqual(self.readiness.state, "approved")
        self.assertEqual(self.readiness.approved_by_id, self.manager)
        self.readiness.with_user(self.manager).write({"review_notes": "Configuration changed."})
        self.assertEqual(self.readiness.state, "draft")
        self.assertFalse(self.readiness.approved_by_id)

    def test_incomplete_checklist_cannot_be_approved(self):
        with patch.object(type(self.readiness), "_get_technical_errors", return_value=[]):
            with self.assertRaises(UserError):
                self.readiness.with_user(self.manager).action_approve()

    def test_public_context_cannot_forge_finance_approval(self):
        with self.assertRaises(UserError):
            self.env["chantier.finance.readiness"].with_context(
                chantier_finance_workflow=True
            ).create({
                "company_id": self.company.id, "state": "approved",
                "approved_by_id": self.manager.id,
            })
        with self.assertRaises(UserError):
            self.readiness.with_user(self.manager).with_context(
                chantier_finance_workflow=True
            ).write({"state": "approved"})

    def test_chantier_invoice_posting_requires_readiness_approval(self):
        invoice = self._draft_invoice()
        with self.assertRaises(UserError):
            invoice.with_user(self.manager).action_post()
        self.readiness.with_user(self.manager).write(self._complete_checklist())
        with patch.object(type(self.readiness), "_get_technical_errors", return_value=[]):
            self.readiness.with_user(self.manager).action_approve()
        invoice.with_user(self.manager).action_post()
        self.assertEqual(invoice.state, "posted")

    def test_direct_posting_path_also_requires_finance_approval(self):
        invoice = self._draft_invoice()
        with self.assertRaises(UserError):
            invoice.with_user(self.manager)._post(soft=False)

    def test_technical_check_requires_both_payment_directions_per_journal(self):
        journal = self.env["account.journal"].create({
            "name": "Incomplete Payment Methods", "code": "FPM1", "type": "bank",
            "company_id": self.company.id,
        })
        journal.outbound_payment_method_line_ids.unlink()
        checks = self.readiness.with_context(lang="en_US")._technical_checks()
        payment_check = next(passed for label, passed, detail in checks if label == "Bank and cash payment methods")
        self.assertFalse(payment_check)

    def test_purchase_bill_values_keep_chantier_and_analytic_source(self):
        vendor = self.env["res.partner"].create({
            "name": "Finance Gate Vendor", "supplier_rank": 1
        })
        material = self.env["product.product"].create({
            "name": "Finance Gate Material", "type": "product"
        })
        request = self.env["chantier.material.request"].create({
            "chantier_id": self.chantier.id,
            "vendor_id": vendor.id,
            "required_date": date(2026, 3, 1),
            "justification": "Finance traceability test",
            "line_ids": [Command.create({
                "product_id": material.id, "product_uom_qty": 1
            })],
        })
        order = self.env["purchase.order"].create({
            "partner_id": vendor.id,
            "company_id": self.company.id,
            "picking_type_id": self.warehouse.in_type_id.id,
            "chantier_material_request_id": request.id,
            "order_line": [Command.create({
                "product_id": material.id,
                "name": material.display_name,
                "product_qty": 1,
                "product_uom": material.uom_po_id.id,
                "price_unit": 100,
                "date_planned": "2026-03-01 12:00:00",
                "chantier_material_request_line_id": request.line_ids.id,
            })],
        })
        invoice_values = order._prepare_invoice()
        line_values = order.order_line._prepare_account_move_line()
        self.assertEqual(invoice_values["chantier_id"], self.chantier.id)
        self.assertEqual(line_values["chantier_id"], self.chantier.id)
        self.assertEqual(
            line_values["analytic_distribution"],
            {str(self.chantier.analytic_account_id.id): 100.0},
        )
