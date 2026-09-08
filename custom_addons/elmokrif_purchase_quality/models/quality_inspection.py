import math

from odoo import Command, _, api, fields, models
from odoo.exceptions import AccessError, UserError, ValidationError
from odoo.tools import float_compare

from .workflow import QUALITY_WORKFLOW_TOKEN

class ChantierQualityInspection(models.Model):
    _name = "chantier.quality.inspection"
    _description = "Chantier Receipt Quality Inspection"
    _inherit = ["mail.thread", "mail.activity.mixin"]
    _order = "id desc"
    _check_company_auto = True

    name = fields.Char(default="New", readonly=True, copy=False, tracking=True)
    receipt_id = fields.Many2one(
        "stock.picking", required=True, readonly=True, copy=False, ondelete="restrict", check_company=True
    )
    purchase_order_id = fields.Many2one(
        "purchase.order", related="receipt_id.purchase_id", store=True, readonly=True
    )
    quality_transfer_id = fields.Many2one(
        "stock.picking", related="receipt_id.chantier_quality_transfer_id", readonly=True
    )
    chantier_id = fields.Many2one(
        "project.project", required=True, readonly=True, check_company=True
    )
    company_id = fields.Many2one("res.company", required=True, readonly=True)
    warehouse_id = fields.Many2one(
        "stock.warehouse", required=True, readonly=True, check_company=True
    )
    inspector_id = fields.Many2one("res.users", readonly=True, tracking=True)
    inspected_at = fields.Datetime(readonly=True, tracking=True)
    state = fields.Selection(
        [("draft", "To Inspect"), ("approved", "Approved and Released")],
        default="draft",
        required=True,
        readonly=True,
        tracking=True,
    )
    notes = fields.Text()
    line_ids = fields.One2many(
        "chantier.quality.inspection.line", "inspection_id", string="Inspection Lines"
    )
    accepted_picking_id = fields.Many2one(
        "stock.picking", readonly=True, copy=False, check_company=True
    )
    rejected_picking_id = fields.Many2one(
        "stock.picking", readonly=True, copy=False, check_company=True
    )
    supplier_return_picking_id = fields.Many2one(
        "stock.picking", readonly=True, copy=False, check_company=True
    )

    _sql_constraints = [
        ("receipt_unique", "unique(receipt_id)", "A receipt can have only one quality inspection."),
    ]

    @api.model_create_multi
    def create(self, vals_list):
        in_workflow = self.env.context.get("_quality_workflow_token") is QUALITY_WORKFLOW_TOKEN
        if not in_workflow:
            raise UserError(_("Quality inspections are created automatically from completed purchase receipts."))
        for values in vals_list:
            if values.get("name", "New") == "New":
                values["name"] = self.env["ir.sequence"].next_by_code(
                    "chantier.quality.inspection"
                ) or "New"
        return super().create(vals_list)

    def write(self, vals):
        in_workflow = self.env.context.get("_quality_workflow_token") is QUALITY_WORKFLOW_TOKEN
        if {"state", "inspector_id", "inspected_at", "accepted_picking_id", "rejected_picking_id", "supplier_return_picking_id"}.intersection(vals) and not in_workflow:
            raise UserError(_("Use the quality approval action to change inspection state."))
        if {"receipt_id", "warehouse_id", "chantier_id", "company_id"}.intersection(vals):
            raise UserError(_("The source receipt and its quality inspection details cannot be changed."))
        if {"line_ids", "receipt_id", "warehouse_id", "chantier_id", "company_id"}.intersection(vals):
            if any(inspection.state != "draft" for inspection in self):
                raise UserError(_("An approved inspection cannot be changed."))
        return super().write(vals)

    def _workflow_write(self, vals):
        return self.with_context(_quality_workflow_token=QUALITY_WORKFLOW_TOKEN).write(vals)

    def unlink(self):
        raise UserError(_("Receipt quality inspections must be retained for audit."))

    def _create_release_picking(self, kind, quantities):
        self.ensure_one()
        source = self.warehouse_id.chantier_quality_location_id
        destination = (
            self.warehouse_id.lot_stock_id
            if kind == "accepted"
            else self.warehouse_id.chantier_quarantine_location_id
        )
        moves = []
        for line, quantity in quantities.items():
            if float_compare(quantity, 0, precision_rounding=line.product_uom_id.rounding) <= 0:
                continue
            move_values = {
                "name": line.product_id.display_name,
                "product_id": line.product_id.id,
                "product_uom_qty": quantity,
                "product_uom": line.product_uom_id.id,
                "location_id": source.id,
                "location_dest_id": destination.id,
                "chantier_quality_inspection_line_id": line.id,
            }
            if line.move_line_id:
                move_values["move_line_ids"] = [Command.create({
                    "product_id": line.product_id.id,
                    "product_uom_id": line.product_uom_id.id,
                    "quantity": quantity,
                    "location_id": source.id,
                    "location_dest_id": destination.id,
                    "lot_id": line.lot_id.id,
                })]
            moves.append(Command.create(move_values))
        if not moves:
            return self.env["stock.picking"]
        picking = self.env["stock.picking"].with_context(
            _quality_workflow_token=QUALITY_WORKFLOW_TOKEN
        ).create({
            "picking_type_id": self.warehouse_id.int_type_id.id,
            "location_id": source.id,
            "location_dest_id": destination.id,
            "origin": "%s / %s" % (self.receipt_id.name, self.name),
            "chantier_quality_inspection_id": self.id,
            "chantier_quality_release_kind": kind,
            "move_ids_without_package": moves,
        })
        picking.action_confirm()
        for move in picking.move_ids:
            if not move.move_line_ids:
                move.quantity = move.product_uom_qty
            move.picked = True
        result = picking.with_context(
            _quality_workflow_token=QUALITY_WORKFLOW_TOKEN,
            skip_backorder=True,
        ).button_validate()
        if isinstance(result, dict):
            raise UserError(_("The quality release could not be completed automatically."))
        return picking

    def action_approve_and_release(self):
        self.check_access_rights("write")
        self.check_access_rule("write")
        if not self.env.user.has_group(
            "elmokrif_purchase_quality.group_chantier_quality_inspector"
        ):
            raise AccessError(_("Only a designated quality inspector can approve a receipt."))
        for inspection in self:
            self.env.cr.execute(
                "SELECT id FROM chantier_quality_inspection WHERE id = %s FOR UPDATE",
                [inspection.id],
            )
            inspection.invalidate_recordset(["state", "accepted_picking_id", "rejected_picking_id"])
            if inspection.state != "draft":
                raise UserError(_("This inspection has already been released."))
            if not inspection.line_ids:
                raise UserError(_("The inspection has no received material lines."))
            accepted = {}
            rejected = {}
            for line in inspection.line_ids:
                line._validate_complete_inspection()
                accepted[line] = line.accepted_qty
                rejected[line] = line.rejected_qty
            inspection.warehouse_id._ensure_chantier_quality_locations()
            accepted_picking = inspection._create_release_picking("accepted", accepted)
            rejected_picking = inspection._create_release_picking("rejected", rejected)
            inspection._workflow_write({
                "state": "approved",
                "inspector_id": self.env.user.id,
                "inspected_at": fields.Datetime.now(),
                "accepted_picking_id": accepted_picking.id,
                "rejected_picking_id": rejected_picking.id,
            })
        return True

    def action_create_supplier_return(self):
        self.check_access_rights("read")
        self.check_access_rule("read")
        if not (
            self.env.user.has_group("elmokrif_purchase_quality.group_chantier_purchase_buyer")
            or self.env.user.has_group("elmokrif_purchase_quality.group_chantier_purchase_approver")
        ):
            raise AccessError(_("Only a chantier buyer or purchase approver can create the supplier return."))
        self.ensure_one()
        self.env.cr.execute(
            "SELECT id FROM chantier_quality_inspection WHERE id = %s FOR UPDATE",
            [self.id],
        )
        self.invalidate_recordset(["state", "supplier_return_picking_id"])
        if self.state != "approved":
            raise UserError(_("Approve the quality inspection before returning rejected material."))
        if self.supplier_return_picking_id:
            raise UserError(_("The rejected-material supplier return already exists."))
        rejected_lines = self.line_ids.filtered(lambda line: line.rejected_qty > 0)
        if not rejected_lines:
            raise UserError(_("This inspection has no rejected material to return."))
        receipt = self.receipt_id
        source = self.warehouse_id.chantier_quarantine_location_id
        destination = receipt.location_id
        moves = []
        for line in rejected_lines:
            move_values = {
                "name": line.product_id.display_name,
                "product_id": line.product_id.id,
                "product_uom_qty": line.rejected_qty,
                "product_uom": line.product_uom_id.id,
                "location_id": source.id,
                "location_dest_id": destination.id,
                "origin_returned_move_id": line.move_id.id,
                "purchase_line_id": line.move_id.purchase_line_id.id,
                "to_refund": True,
                "chantier_quality_inspection_line_id": line.id,
            }
            if line.move_line_id:
                move_values["move_line_ids"] = [Command.create({
                    "product_id": line.product_id.id,
                    "product_uom_id": line.product_uom_id.id,
                    "quantity": line.rejected_qty,
                    "location_id": source.id,
                    "location_dest_id": destination.id,
                    "lot_id": line.lot_id.id,
                })]
            moves.append(Command.create(move_values))
        return_type = receipt.picking_type_id.return_picking_type_id or receipt.picking_type_id
        supplier_return = self.env["stock.picking"].sudo().with_context(
            _quality_workflow_token=QUALITY_WORKFLOW_TOKEN
        ).create({
            "picking_type_id": return_type.id,
            "partner_id": receipt.partner_id.id,
            "location_id": source.id,
            "location_dest_id": destination.id,
            "return_id": receipt.id,
            "origin": _("Return rejected material from %s") % receipt.name,
            "chantier_purchase_request_id": receipt.chantier_purchase_request_id.id,
            "chantier_quality_inspection_id": self.id,
            "chantier_quality_release_kind": "supplier_return",
            "move_ids_without_package": moves,
        })
        self.sudo()._workflow_write({"supplier_return_picking_id": supplier_return.id})
        return {
            "type": "ir.actions.act_window",
            "name": _("Rejected Material Supplier Return"),
            "res_model": "stock.picking",
            "view_mode": "form",
            "res_id": supplier_return.id,
        }


class ChantierQualityInspectionLine(models.Model):
    _name = "chantier.quality.inspection.line"
    _description = "Chantier Quality Inspection Line"
    _check_company_auto = True

    inspection_id = fields.Many2one(
        "chantier.quality.inspection", required=True, ondelete="cascade"
    )
    company_id = fields.Many2one(
        "res.company", related="inspection_id.company_id", store=True, readonly=True
    )
    move_id = fields.Many2one("stock.move", required=True, readonly=True, ondelete="restrict")
    move_line_id = fields.Many2one(
        "stock.move.line", string="Receipt Operation", readonly=True, ondelete="restrict"
    )
    lot_id = fields.Many2one(
        "stock.lot", related="move_line_id.lot_id", store=True, readonly=True
    )
    product_id = fields.Many2one("product.product", required=True, readonly=True)
    product_uom_id = fields.Many2one("uom.uom", required=True, readonly=True)
    received_qty = fields.Float(required=True, readonly=True)
    accepted_qty = fields.Float()
    rejected_qty = fields.Float()
    condition_ok = fields.Boolean(string="Condition Accepted")
    specification_ok = fields.Boolean(string="Specification Accepted")
    certificate_reference = fields.Char()
    rejection_reason = fields.Char()

    @api.model_create_multi
    def create(self, vals_list):
        if self.env.context.get("_quality_workflow_token") is not QUALITY_WORKFLOW_TOKEN:
            raise AccessError(_("Inspection material lines are created from the source receipt."))
        return super().create(vals_list)

    def write(self, vals):
        if {"inspection_id", "move_id", "move_line_id", "product_id", "product_uom_id", "received_qty"}.intersection(vals):
            raise AccessError(_("The received material, quantity and source operation cannot be changed."))
        if any(line.inspection_id.state != "draft" for line in self):
            raise UserError(_("Approved inspection lines cannot be changed."))
        return super().write(vals)

    def unlink(self):
        raise UserError(_("All received material lines must remain in the quality inspection."))

    @api.constrains("accepted_qty", "rejected_qty", "received_qty")
    def _check_inspected_quantity_bounds(self):
        for line in self:
            if not all(math.isfinite(quantity) for quantity in (line.accepted_qty, line.rejected_qty, line.received_qty)):
                raise ValidationError(_("Inspection quantities must be finite numbers."))
            rounding = line.product_uom_id.rounding
            if (
                float_compare(line.accepted_qty, 0, precision_rounding=rounding) < 0
                or float_compare(line.rejected_qty, 0, precision_rounding=rounding) < 0
            ):
                raise ValidationError(_("Accepted and rejected quantities cannot be negative."))
            if float_compare(
                line.accepted_qty + line.rejected_qty,
                line.received_qty,
                precision_rounding=rounding,
            ) > 0:
                raise ValidationError(_("Accepted plus rejected quantity cannot exceed the received quantity."))

    def _validate_complete_inspection(self):
        for line in self:
            rounding = line.product_uom_id.rounding
            if float_compare(
                line.accepted_qty + line.rejected_qty,
                line.received_qty,
                precision_rounding=rounding,
            ) != 0:
                raise ValidationError(_("Accepted plus rejected quantity must equal the received quantity."))
            if line.rejected_qty and not line.rejection_reason:
                raise ValidationError(_("Enter a rejection reason for rejected material."))
            if line.accepted_qty and not (line.condition_ok and line.specification_ok):
                raise ValidationError(_(
                    "Condition and specification checks must both pass before material is accepted."
                ))
