from odoo import _, api, fields, models
from odoo.exceptions import UserError


class StockPicking(models.Model):
    _inherit = "stock.picking"

    chantier_id = fields.Many2one("project.project", string="Chantier", copy=True, check_company=True)
    material_request_id = fields.Many2one("chantier.material.request", string="Material Request", copy=True, readonly=True, check_company=True)
    chantier_operation = fields.Selection([
        ("delivery", "Delivery to Site"),
        ("consumption", "Consumption"),
        ("return", "Return to Warehouse"),
        ("missing", "Missing Material"),
    ], string="Chantier Material Operation", default="delivery", tracking=True)

    def _get_chantier_operation_locations(self, chantier, operation):
        """Return the system-owned locations for one chantier operation."""
        if operation == "delivery":
            return chantier.warehouse_id.lot_stock_id, chantier.site_location_id
        if operation == "return":
            return chantier.site_location_id, chantier.warehouse_id.lot_stock_id
        chantier.warehouse_id._ensure_chantier_operation_locations()
        destination = (
            chantier.warehouse_id.chantier_consumption_location_id
            if operation == "consumption"
            else chantier.warehouse_id.chantier_missing_location_id
        )
        return chantier.site_location_id, destination

    @api.model
    def _prepare_chantier_operation_values(self, vals):
        """Normalize a manual chantier move that started from a stock action."""
        values = dict(vals)
        returned_picking = self.sudo().browse(values.get("return_id"))
        if returned_picking.chantier_id:
            reverse_operation = {
                "delivery": "return",
                "return": "delivery",
            }.get(returned_picking.chantier_operation)
            if reverse_operation:
                values.update({
                    "chantier_id": returned_picking.chantier_id.id,
                    "chantier_operation": reverse_operation,
                    "material_request_id": False,
                })
        chantier = self.env["project.project"].sudo().browse(values.get("chantier_id"))
        if not chantier or values.get("material_request_id"):
            return values
        operation = values.get("chantier_operation", "delivery")
        source, destination = self._get_chantier_operation_locations(
            chantier, operation
        )
        values.update({
            "picking_type_id": chantier.warehouse_id.int_type_id.id,
            "location_id": source.id,
            "location_dest_id": destination.id,
        })
        for command in values.get("move_ids_without_package", []):
            if command[0] in (0, 1) and command[2]:
                command[2].update({
                    "location_id": source.id,
                    "location_dest_id": destination.id,
                })
        return values

    @api.model_create_multi
    def create(self, vals_list):
        return super().create([
            self._prepare_chantier_operation_values(vals) for vals in vals_list
        ])

    def write(self, vals):
        tracked_fields = {
            "chantier_id", "chantier_operation", "location_id",
            "location_dest_id", "picking_type_id",
        }
        if not tracked_fields.intersection(vals):
            return super().write(vals)
        for picking in self:
            values = dict(vals)
            chantier_id = values.get("chantier_id", picking.chantier_id.id)
            operation = values.get("chantier_operation", picking.chantier_operation)
            if chantier_id and not picking.material_request_id:
                values = self._prepare_chantier_operation_values({
                    **values,
                    "chantier_id": chantier_id,
                    "chantier_operation": operation,
                })
            super(StockPicking, picking).write(values)
        return True

    @api.onchange("chantier_id", "chantier_operation")
    def _onchange_chantier_operation(self):
        for picking in self.filtered("chantier_id"):
            chantier = picking.chantier_id
            source, destination = picking._get_chantier_operation_locations(
                chantier, picking.chantier_operation
            )
            picking.picking_type_id = chantier.warehouse_id.int_type_id
            picking.location_id = source
            picking.location_dest_id = destination

    @api.constrains("chantier_id", "chantier_operation", "location_id", "location_dest_id")
    def _check_chantier_operation_locations(self):
        for picking in self.filtered("chantier_id"):
            chantier = picking.sudo().chantier_id
            expected = picking._get_chantier_operation_locations(
                chantier, picking.chantier_operation
            )
            if picking.location_id != expected[0] or picking.location_dest_id != expected[1]:
                raise UserError(_("The locations do not match the selected chantier material operation."))

    def _action_done(self):
        result = super()._action_done()
        self.sudo().mapped("material_request_id")._update_delivery_state()
        return result


class StockMove(models.Model):
    _inherit = "stock.move"

    material_request_line_id = fields.Many2one(
        "chantier.material.request.line",
        string="Material Request Line",
        copy=True,
        readonly=True,
        index=True,
        ondelete="set null",
        check_company=True,
    )
    company_currency_id = fields.Many2one(
        "res.currency",
        string="Company Currency",
        related="company_id.currency_id",
        store=True,
        readonly=True,
    )
    chantier_valuation_amount = fields.Monetary(
        string="Chantier Stock Valuation",
        currency_field="company_currency_id",
        compute="_compute_chantier_valuation",
        store=True,
        copy=False,
        help="Historical value from Odoo stock valuation layers for a completed chantier consumption or missing-material move.",
    )
    chantier_valuation_status = fields.Selection(
        [
            ("not_applicable", "Not Applicable"),
            ("valued", "Valued"),
            ("unvalued", "No Valuation Layer"),
        ],
        compute="_compute_chantier_valuation",
        store=True,
        copy=False,
    )

    @api.depends(
        "state",
        "picking_id.chantier_id",
        "picking_id.chantier_operation",
        "stock_valuation_layer_ids.value",
    )
    def _compute_chantier_valuation(self):
        for move in self:
            eligible = (
                move.state == "done"
                and move.picking_id.chantier_id
                and move.picking_id.chantier_operation in ("consumption", "missing")
            )
            if not eligible:
                move.chantier_valuation_amount = 0.0
                move.chantier_valuation_status = "not_applicable"
                continue
            layers = move.stock_valuation_layer_ids
            move.chantier_valuation_amount = -sum(layers.mapped("value"))
            move.chantier_valuation_status = "valued" if layers else "unvalued"

    @api.model
    def _prepare_merge_moves_distinct_fields(self):
        """Keep separate request lines traceable when they use one product."""
        return [
            *super()._prepare_merge_moves_distinct_fields(),
            "material_request_line_id",
        ]
