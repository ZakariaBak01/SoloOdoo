from odoo import _, api, fields, models
from odoo.osv import expression


class ProjectProject(models.Model):
    _inherit = "project.project"

    sale_order_ids = fields.One2many(
        "sale.order",
        "chantier_id",
        string="Sales Orders",
        readonly=True,
    )
    sale_order_count = fields.Integer(
        string="Sales",
        compute="_compute_sale_order_count",
        groups="sales_team.group_sale_salesman",
    )

    def _sale_order_domain(self):
        self.ensure_one()
        return expression.OR(
            [
                [("chantier_id", "=", self.id)],
                [("order_line.chantier_id", "=", self.id)],
            ]
        )

    @api.depends("sale_order_ids", "sale_order_ids.order_line.chantier_id")
    def _compute_sale_order_count(self):
        SaleOrder = self.env["sale.order"]
        for chantier in self:
            chantier.sale_order_count = (
                SaleOrder.search_count(chantier._sale_order_domain())
                if chantier.is_chantier
                else 0
            )

    def action_view_sale_orders(self):
        self.ensure_one()
        return {
            "type": "ir.actions.act_window",
            "name": _("Sales"),
            "res_model": "sale.order",
            "view_mode": "tree,form",
            "domain": self._sale_order_domain(),
            "context": {
                "default_chantier_id": self.id,
                "search_default_chantier_id": self.id,
            },
        }

    def _get_chantier_closure_blockers(self):
        blockers = super()._get_chantier_closure_blockers()
        SaleOrder = self.env["sale.order"]
        for chantier in self:
            linked_domain = chantier._sale_order_domain()
            quotations = SaleOrder.search_count(
                expression.AND([linked_domain, [("state", "in", ["draft", "sent"])]])
            )
            invoiceable = SaleOrder.search_count(
                expression.AND(
                    [
                        linked_domain,
                        [("state", "=", "sale"), ("invoice_status", "=", "to invoice")],
                    ]
                )
            )
            if quotations:
                blockers.append(_("%(count)s unresolved quotation(s)", count=quotations))
            if invoiceable:
                blockers.append(_("%(count)s invoiceable order(s)", count=invoiceable))
        return blockers
