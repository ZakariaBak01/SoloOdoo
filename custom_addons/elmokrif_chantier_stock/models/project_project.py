from markupsafe import Markup, escape

from odoo import _, api, fields, models


class ProjectProject(models.Model):
    _inherit = "project.project"

    material_request_ids = fields.One2many("chantier.material.request", "chantier_id", string="Material Requests")
    material_picking_ids = fields.One2many("stock.picking", "chantier_id", string="Material Transfers")
    material_request_count = fields.Integer(compute="_compute_material_request_count")
    material_cost = fields.Monetary(compute="_compute_material_cost", currency_field="currency_id", string="Material Cost (Current Cost Estimate)", compute_sudo=True)
    material_summary = fields.Html(
        compute="_compute_material_summary",
        string="Materials Summary",
        compute_sudo=True,
        sanitize=False,
    )

    def _compute_material_request_count(self):
        for project in self:
            project.material_request_count = len(project.material_request_ids)

    @api.depends(
        "material_picking_ids.move_ids.state",
        "material_picking_ids.move_ids.quantity",
        "material_picking_ids.move_ids.product_uom",
        "material_picking_ids.move_ids.product_id",
        "material_picking_ids.move_ids.product_id.standard_price",
        "material_picking_ids.chantier_operation",
    )
    def _compute_material_cost(self):
        for project in self:
            moves = self.env["stock.move"].search([
                ("picking_id.chantier_id", "=", project.id),
                ("picking_id.chantier_operation", "in", ("consumption", "missing")),
                ("state", "=", "done"),
            ])
            project.material_cost = sum(
                move.product_uom._compute_quantity(move.quantity, move.product_id.uom_id)
                * move.product_id.with_company(project.company_id).standard_price
                for move in moves
            )

    @api.depends(
        "material_picking_ids.move_ids.state",
        "material_picking_ids.move_ids.quantity",
        "material_picking_ids.move_ids.product_uom",
        "material_picking_ids.move_ids.product_id",
        "material_picking_ids.move_ids.product_id.standard_price",
        "material_picking_ids.chantier_operation",
    )
    def _compute_material_summary(self):
        operations = ("delivery", "consumption", "return", "missing")
        headings = {
            "delivery": _("Received"),
            "consumption": _("Consumed"),
            "return": _("Returned"),
            "missing": _("Missing"),
        }
        for project in self:
            moves = self.env["stock.move"].search([
                ("picking_id.chantier_id", "=", project.id),
                ("picking_id.chantier_operation", "in", operations),
                ("state", "=", "done"),
            ])
            totals = {}
            for move in moves:
                product = move.product_id
                quantities = totals.setdefault(product.id, {
                    "product": product,
                    **{operation: 0.0 for operation in operations},
                })
                quantities[move.picking_id.chantier_operation] += (
                    move.product_uom._compute_quantity(move.quantity, product.uom_id)
                )

            rows = []
            for values in totals.values():
                remaining = (
                    values["delivery"]
                    - values["consumption"]
                    - values["return"]
                    - values["missing"]
                )
                current_cost = (
                    values["consumption"] + values["missing"]
                ) * values["product"].with_company(project.company_id).standard_price
                rows.append(Markup(
                    "<tr><td>{}</td><td>{}</td><td>{:.2f}</td><td>{:.2f}</td>"
                    "<td>{:.2f}</td><td>{:.2f}</td><td>{:.2f}</td><td>{:.2f}</td></tr>"
                ).format(
                    escape(values["product"].display_name),
                    escape(values["product"].uom_id.display_name),
                    values["delivery"], values["consumption"], values["return"],
                    values["missing"], remaining, current_cost,
                ))
            header = Markup(
                "<tr><th>{}</th><th>{}</th><th>{}</th><th>{}</th>"
                "<th>{}</th><th>{}</th><th>{}</th><th>{}</th></tr>"
            ).format(
                escape(_("Product")), escape(_("Unit")), escape(headings["delivery"]),
                escape(headings["consumption"]), escape(headings["return"]),
                escape(headings["missing"]), escape(_("Remaining")), escape(_("Current Cost")),
            )
            project.material_summary = Markup(
                "<table class=\"table table-sm o_chantier_material_summary\"><thead>{}"
                "</thead><tbody>{}</tbody></table>"
            ).format(header, Markup().join(rows)) if rows else ""

    def action_view_material_requests(self):
        self.ensure_one()
        return {
            "type": "ir.actions.act_window", "name": "Material Requests",
            "res_model": "chantier.material.request", "view_mode": "tree,form",
            "domain": [("chantier_id", "=", self.id)],
            "context": {
                "default_chantier_id": self.id,
                "default_company_id": self.company_id.id,
            },
        }

    def action_create_material_operation(self):
        self.ensure_one()
        return {
            "type": "ir.actions.act_window", "name": "Material Operation",
            "res_model": "stock.picking", "view_mode": "form",
            "target": "current",
            "context": {
                "default_picking_type_id": self.warehouse_id.int_type_id.id,
                "default_chantier_id": self.id,
                "default_location_id": self.site_location_id.id,
            },
        }
