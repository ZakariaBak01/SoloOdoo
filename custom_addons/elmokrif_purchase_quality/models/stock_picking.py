from odoo import Command, _, api, fields, models
from odoo.exceptions import AccessError, UserError
from odoo.tools import float_compare

from .workflow import QUALITY_WORKFLOW_TOKEN

class StockPicking(models.Model):
    _inherit = "stock.picking"

    chantier_purchase_request_id = fields.Many2one(
        "chantier.material.request",
        string="Chantier Purchase Request",
        copy=False,
        readonly=True,
        check_company=True,
    )
    chantier_quality_required = fields.Boolean(copy=False, readonly=True)
    chantier_quality_inspection_id = fields.Many2one(
        "chantier.quality.inspection",
        string="Quality Inspection",
        copy=False,
        readonly=True,
        check_company=True,
    )
    chantier_quality_release_kind = fields.Selection(
        [
            ("accepted", "Accepted Release"),
            ("rejected", "Quarantine"),
            ("supplier_return", "Supplier Return"),
        ],
        copy=False,
        readonly=True,
    )
    chantier_quality_transfer_id = fields.Many2one(
        "stock.picking",
        string="Input to Quality Transfer",
        copy=False,
        readonly=True,
        check_company=True,
    )
    chantier_quality_source_receipt_id = fields.Many2one(
        "stock.picking",
        string="Source Purchase Receipt",
        copy=False,
        readonly=True,
        check_company=True,
    )

    @api.model_create_multi
    def create(self, vals_list):
        protected = {
            "chantier_purchase_request_id", "chantier_quality_required",
            "chantier_quality_inspection_id", "chantier_quality_release_kind",
            "chantier_quality_transfer_id", "chantier_quality_source_receipt_id",
        }
        in_workflow = self.env.context.get("_quality_workflow_token") is QUALITY_WORKFLOW_TOKEN
        if not in_workflow and (any(protected.intersection(values) for values in vals_list) or any("default_" + field in self.env.context for field in protected)):
            raise AccessError(_("Quality-routing links are managed by the purchase and quality workflows."))
        return super().create(vals_list)

    def write(self, vals):
        protected = {
            "chantier_purchase_request_id", "chantier_quality_required",
            "chantier_quality_inspection_id", "chantier_quality_release_kind",
            "chantier_quality_transfer_id", "chantier_quality_source_receipt_id",
        }
        in_workflow = self.env.context.get("_quality_workflow_token") is QUALITY_WORKFLOW_TOKEN
        if protected.intersection(vals) and not in_workflow:
            raise AccessError(_("Quality-routing links are managed by the purchase and quality workflows."))
        return super().write(vals)

    def _is_chantier_quality_receipt(self):
        self.ensure_one()
        return bool(
            self.chantier_quality_required
            and self.chantier_purchase_request_id
            and self.picking_type_id.code == "incoming"
        )

    def _create_backorder_picking(self):
        backorder = super(StockPicking, self.with_context(
            _quality_workflow_token=QUALITY_WORKFLOW_TOKEN
        ))._create_backorder_picking()
        if self._is_chantier_quality_receipt():
            backorder.with_context(_quality_workflow_token=QUALITY_WORKFLOW_TOKEN).write({
                "chantier_purchase_request_id": self.chantier_purchase_request_id.id,
                "chantier_quality_required": True,
            })
        return backorder

    def _action_done(self):
        self._check_quality_routes()
        result = super()._action_done()
        for picking in self.filtered(lambda item: item._is_chantier_quality_receipt()):
            picking._ensure_input_to_quality_transfer()
            picking._ensure_quality_inspection()
        return result

    def _quality_move_values(self, move, move_line, quantity, source, destination):
        values = {
            "name": move.product_id.display_name,
            "product_id": move.product_id.id,
            "product_uom_qty": quantity,
            "product_uom": move_line.product_uom_id.id if move_line else move.product_uom.id,
            "location_id": source.id,
            "location_dest_id": destination.id,
            "chantier_quality_receipt_move_id": move.id,
        }
        if move_line:
            values["move_line_ids"] = [Command.create({
                "product_id": move_line.product_id.id,
                "product_uom_id": move_line.product_uom_id.id,
                "quantity": quantity,
                "location_id": source.id,
                "location_dest_id": destination.id,
                "lot_id": move_line.lot_id.id,
            })]
        return values

    def _ensure_input_to_quality_transfer(self):
        self.ensure_one()
        if self.chantier_quality_transfer_id:
            return self.chantier_quality_transfer_id
        warehouse = self.picking_type_id.warehouse_id
        warehouse._ensure_chantier_quality_locations()
        moves = []
        for move in self.move_ids.filtered(lambda item: item.state == "done" and item.quantity > 0):
            receipt_lines = move.move_line_ids.filtered(lambda item: item.quantity > 0)
            if receipt_lines:
                for move_line in receipt_lines:
                    moves.append(Command.create(self._quality_move_values(
                        move,
                        move_line,
                        move_line.quantity,
                        warehouse.chantier_input_location_id,
                        warehouse.chantier_quality_location_id,
                    )))
            else:
                moves.append(Command.create(self._quality_move_values(
                    move,
                    self.env["stock.move.line"],
                    move.quantity,
                    warehouse.chantier_input_location_id,
                    warehouse.chantier_quality_location_id,
                )))
        if not moves:
            return self.env["stock.picking"]
        transfer = self.env["stock.picking"].sudo().with_context(
            _quality_workflow_token=QUALITY_WORKFLOW_TOKEN
        ).create({
            "picking_type_id": warehouse.int_type_id.id,
            "location_id": warehouse.chantier_input_location_id.id,
            "location_dest_id": warehouse.chantier_quality_location_id.id,
            "origin": _("Quality routing for %s") % self.name,
            "chantier_purchase_request_id": self.chantier_purchase_request_id.id,
            "chantier_quality_source_receipt_id": self.id,
            "move_ids_without_package": moves,
        })
        self.sudo().with_context(_quality_workflow_token=QUALITY_WORKFLOW_TOKEN).write({
            "chantier_quality_transfer_id": transfer.id
        })
        transfer.action_confirm()
        for move in transfer.move_ids:
            if not move.move_line_ids:
                move.quantity = move.product_uom_qty
            move.picked = True
        validation = transfer.with_context(skip_backorder=True).button_validate()
        if isinstance(validation, dict):
            raise UserError(_("The Input to Quality transfer could not be completed automatically."))
        return transfer

    def _ensure_quality_inspection(self):
        self.ensure_one()
        inspection = self.chantier_quality_inspection_id or self.env[
            "chantier.quality.inspection"
        ].search([("receipt_id", "=", self.id)], limit=1)
        if inspection:
            if not self.chantier_quality_inspection_id:
                self.sudo().with_context(_quality_workflow_token=QUALITY_WORKFLOW_TOKEN).write({
                    "chantier_quality_inspection_id": inspection.id
                })
            return inspection
        lines = []
        for move in self.move_ids.filtered(lambda item: item.state == "done" and item.quantity > 0):
            received_move_lines = move.move_line_ids.filtered(
                lambda item: item.quantity > 0
            )
            if received_move_lines:
                for move_line in received_move_lines:
                    lines.append((0, 0, {
                        "move_id": move.id,
                        "move_line_id": move_line.id,
                        "product_id": move_line.product_id.id,
                        "product_uom_id": move_line.product_uom_id.id,
                        "received_qty": move_line.quantity,
                    }))
            else:
                lines.append((0, 0, {
                    "move_id": move.id,
                    "product_id": move.product_id.id,
                    "product_uom_id": move.product_uom.id,
                    "received_qty": move.quantity,
                }))
        if not lines:
            return self.env["chantier.quality.inspection"]
        inspection = self.env["chantier.quality.inspection"].sudo().with_context(
            _quality_workflow_token=QUALITY_WORKFLOW_TOKEN
        ).create({
            "receipt_id": self.id,
            "company_id": self.company_id.id,
            "warehouse_id": self.picking_type_id.warehouse_id.id,
            "chantier_id": self.chantier_purchase_request_id.chantier_id.id,
            "line_ids": lines,
        })
        self.sudo().with_context(_quality_workflow_token=QUALITY_WORKFLOW_TOKEN).write({
            "chantier_quality_inspection_id": inspection.id
        })
        return inspection

    def button_validate(self):
        self._check_quality_routes()
        return super().button_validate()

    def _check_quality_routes(self):
        for picking in self:
            operations = picking.move_ids.filtered(lambda move: move.state != "cancel")
            destinations = picking.location_dest_id | operations.location_dest_id | operations.move_line_ids.location_dest_id
            sources = picking.location_id | operations.location_id | operations.move_line_ids.location_id
            if picking._is_chantier_quality_receipt():
                warehouse = picking.picking_type_id.warehouse_id
                warehouse._ensure_chantier_quality_locations()
                valid_destinations = self.env["stock.location"].search_count([
                    ("id", "in", destinations.ids),
                    ("id", "child_of", warehouse.chantier_input_location_id.id),
                ])
                if valid_destinations != len(destinations):
                    raise UserError(_(
                        "A chantier purchase receipt must enter the warehouse Input location."
                    ))
            warehouses = self.env["stock.warehouse"].search([
                ("company_id", "=", picking.company_id.id),
                ("chantier_input_location_id", "!=", False),
                ("chantier_quality_location_id", "!=", False),
                ("chantier_quarantine_location_id", "!=", False),
            ])
            protected_roots = (
                warehouses.mapped("chantier_input_location_id")
                | warehouses.mapped("chantier_quality_location_id")
                | warehouses.mapped("chantier_quarantine_location_id")
            )
            is_protected_source = protected_roots and self.env["stock.location"].search_count([
                ("id", "in", sources.ids),
                ("id", "child_of", protected_roots.ids),
            ])
            if is_protected_source and not picking._is_authorized_quality_movement():
                raise UserError(_(
                    "Move material from Input, Quality, or Quarantine only through its "
                    "linked quality workflow. Direct transfers are blocked."
                ))

    def _is_authorized_quality_movement(self):
        self.ensure_one()
        if self.chantier_quality_source_receipt_id:
            receipt = self.chantier_quality_source_receipt_id
            warehouse = receipt.picking_type_id.warehouse_id
            return bool(
                receipt.state == "done"
                and receipt.chantier_quality_transfer_id == self
                and self.location_id == warehouse.chantier_input_location_id
                and self.location_dest_id == warehouse.chantier_quality_location_id
                and self.move_ids
                and all(
                    move.chantier_quality_receipt_move_id in receipt.move_ids
                    for move in self.move_ids
                )
            )
        inspection = self.chantier_quality_inspection_id
        if not inspection or not self.chantier_quality_release_kind:
            return False
        warehouse = inspection.warehouse_id
        expected = {
            "accepted": (
                warehouse.chantier_quality_location_id,
                warehouse.lot_stock_id,
            ),
            "rejected": (
                warehouse.chantier_quality_location_id,
                warehouse.chantier_quarantine_location_id,
            ),
            "supplier_return": (
                warehouse.chantier_quarantine_location_id,
                inspection.receipt_id.location_id,
            ),
        }.get(self.chantier_quality_release_kind)
        if not expected or self.location_id != expected[0] or self.location_dest_id != expected[1]:
            return False
        quantities = {}
        for move in self.move_ids.filtered(lambda item: item.state != "cancel"):
            line = move.chantier_quality_inspection_line_id
            if (
                line.inspection_id != inspection
                or move.product_id != line.product_id
                or move.product_uom.category_id != line.product_uom_id.category_id
                or move.location_id != expected[0]
                or move.location_dest_id != expected[1]
                or any(
                    operation.location_id != expected[0]
                    or operation.location_dest_id != expected[1]
                    or operation.product_id != line.product_id
                    or operation.lot_id != line.lot_id
                    for operation in move.move_line_ids
                )
            ):
                return False
            quantities[line] = quantities.get(line, 0.0) + move.product_uom._compute_quantity(
                move.quantity, line.product_uom_id, round=False
            )
        for line, quantity in quantities.items():
            approved_quantity = line.accepted_qty if self.chantier_quality_release_kind == "accepted" else line.rejected_qty
            if float_compare(quantity, approved_quantity, precision_rounding=line.product_uom_id.rounding) > 0:
                return False
        valid_state = (
            inspection.state == "draft"
            if self.chantier_quality_release_kind in ("accepted", "rejected")
            else inspection.state == "approved"
        )
        return bool(
            valid_state
            and self.move_ids
            and all(
                move.chantier_quality_inspection_line_id.inspection_id == inspection
                for move in self.move_ids
            )
        )


class StockMove(models.Model):
    _inherit = "stock.move"

    chantier_quality_inspection_line_id = fields.Many2one(
        "chantier.quality.inspection.line",
        string="Quality Inspection Line",
        copy=False,
        readonly=True,
        ondelete="restrict",
        check_company=True,
    )
    chantier_quality_receipt_move_id = fields.Many2one(
        "stock.move",
        string="Quality Source Receipt Move",
        copy=False,
        readonly=True,
        ondelete="restrict",
        check_company=True,
    )

    @api.model_create_multi
    def create(self, vals_list):
        protected = {"chantier_quality_inspection_line_id", "chantier_quality_receipt_move_id"}
        in_workflow = self.env.context.get("_quality_workflow_token") is QUALITY_WORKFLOW_TOKEN
        if not in_workflow and (any(protected.intersection(values) for values in vals_list) or any("default_" + field in self.env.context for field in protected)):
            raise AccessError(_("Quality stock-move links are managed by the quality workflow."))
        return super().create(vals_list)

    def write(self, vals):
        protected = {"chantier_quality_inspection_line_id", "chantier_quality_receipt_move_id"}
        if protected.intersection(vals) and self.env.context.get("_quality_workflow_token") is not QUALITY_WORKFLOW_TOKEN:
            raise AccessError(_("Quality stock-move links are managed by the quality workflow."))
        return super().write(vals)
