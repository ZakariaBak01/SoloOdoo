from odoo.tests import TransactionCase, tagged


@tagged("post_install", "-at_install")
class TestConstructionTenderBidLine(TransactionCase):
    def test_boq_line_provides_the_analytic_widget_precision(self):
        self.assertIn("analytic_precision", self.env["construction.boq.line"]._fields)

    def test_incomplete_form_line_defers_uom_normalization(self):
        line = self.env["construction.tender.bid.line"].new({
            "quoted_quantity": 2.0,
            "quoted_unit_rate": 12.5,
        })

        line._compute_amounts()

        self.assertEqual(line.quoted_amount, 25.0)
        self.assertEqual(line.normalized_unit_rate, 0.0)
        self.assertEqual(line.normalized_amount, 0.0)
        self.assertEqual(line.variance_percent, 0.0)
