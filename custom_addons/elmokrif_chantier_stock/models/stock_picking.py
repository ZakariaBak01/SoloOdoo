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

    def _get_chantier_loss_location(self, company):
        """Return the company's inventory-adjustment location for site losses."""
        location = self.env["stock.location"].search(
            [
                ("usage", "=", "inventory"),
                "|",
                ("company_id", "=", False),
                ("company_id", "=", company.id),
            ],
            limit=1,
        )
        if not location:
            raise UserError(
                _("Create an inventory adjustment location before recording material consumption or loss.")
            )
        return location

    def _get_chantier_operation_locations(self, chantier, operation):
        """Return the system-owned locations for one chantier operation."""
        if operation == "delivery":
            return chantier.warehouse_id.lot_stock_id, chantier.site_location_id
        if operation == "return":
            return chantier.site_location_id, chantier.warehouse_id.lot_stock_id
        return chantier.site_location_id, self._get_chantier_loss_location(
            chantier.company_id
        )

    @api.model
    def _prepare_chantier_operation_values(self, vals):
        """Normalize a manual chantier move that started from a stock action."""
        chantier = self.env["project.project"].browse(vals.get("chantier_id"))
        if not chantier or vals.get("material_request_id"):
            return vals
        operation = vals.get("chantier_operation", "delivery")
        source, destination = self._get_chantier_operation_locations(
            chantier, operation
        )
        values = dict(vals)
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
            chantier = picking.chantier_id
            expected = picking._get_chantier_operation_locations(
                chantier, picking.chantier_operation
            )
            if picking.location_id != expected[0] or picking.location_dest_id != expected[1]:
                raise UserError(_("The locations do not match the selected chantier material operation."))

    def _action_done(self):
        result = super()._action_done()
        self.mapped("material_request_id")._update_delivery_state()
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

    @api.model
    def _prepare_merge_moves_distinct_fields(self):
        """Keep separate request lines traceable when they use one product."""
        return [
            *super()._prepare_merge_moves_distinct_fields(),
            "material_request_line_id",
        ]
