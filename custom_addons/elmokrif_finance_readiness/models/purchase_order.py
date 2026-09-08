from odoo import models


class PurchaseOrder(models.Model):
    _inherit = "purchase.order"

    def _prepare_invoice(self):
        values = super()._prepare_invoice()
        if self.chantier_id:
            values["chantier_id"] = self.chantier_id.id
        return values


class PurchaseOrderLine(models.Model):
    _inherit = "purchase.order.line"

    def _prepare_account_move_line(self, move=False):
        values = super()._prepare_account_move_line(move=move)
        chantier = self.order_id.chantier_id
        if chantier:
            values["chantier_id"] = chantier.id
            if chantier.analytic_account_id and not values.get("analytic_distribution"):
                values["analytic_distribution"] = {
                    str(chantier.analytic_account_id.id): 100.0
                }
        return values
