import math

from odoo import _, api, fields, models
from odoo.exceptions import AccessError, UserError, ValidationError
from odoo.tools import float_compare

_CONSUMPTION_WORKFLOW_TOKEN = object()

class ChantierMaterialConsumption(models.Model):
    _name = "chantier.material.consumption"
    _description = "Approved Chantier Material Consumption"
    _inherit = ["mail.thread", "mail.activity.mixin"]
    _order = "operation_date desc, id desc"
    _check_company_auto = True

    name = fields.Char(default="New", readonly=True, copy=False, tracking=True)
    company_id = fields.Many2one(
        "res.company", required=True, default=lambda self: self.env.company,
        tracking=True,
    )
    chantier_id = fields.Many2one(
        "project.project", required=True, check_company=True, tracking=True,
        domain="[('is_chantier', '=', True), ('company_id', '=', company_id)]",
    )
    operation_date = fields.Date(default=fields.Date.context_today, required=True, tracking=True)
    work_type = fields.Selection([
        ("construction", "Construction"), ("carpentry", "Carpentry"),
        ("finishing", "Finishing"),
    ], required=True, tracking=True)
    requested_by_id = fields.Many2one(
        "res.users", required=True, readonly=True, default=lambda self: self.env.user,
    )
    approved_by_id = fields.Many2one("res.users", readonly=True, copy=False, tracking=True)
    approved_at = fields.Datetime(readonly=True, copy=False, tracking=True)
    state = fields.Selection([
        ("draft", "Draft"), ("submitted", "Submitted"),
        ("approved", "Approved"), ("done", "Consumed"), ("cancel", "Cancelled"),
    ], default="draft", readonly=True, required=True, copy=False, tracking=True)
    line_ids = fields.One2many("chantier.material.consumption.line", "consumption_id", required=True)
    picking_id = fields.Many2one("stock.picking", readonly=True, copy=False, check_company=True)

    _sql_constraints = [
        ("picking_unique", "unique(picking_id)", "A stock movement can belong to only one consumption."),
    ]

    @api.model_create_multi
    def create(self, values_list):
        workflow_fields = {"state", "picking_id", "approved_by_id", "approved_at"}
        in_workflow = self.env.context.get("_elmokrif_consumption_workflow_token") is _CONSUMPTION_WORKFLOW_TOKEN
        if not in_workflow and any(workflow_fields.intersection(values) for values in values_list):
            raise UserError(_("Consumption workflow evidence is managed by the consumption actions."))
        for values in values_list:
            if not in_workflow:
                values.update({"state": "draft", "picking_id": False, "approved_by_id": False, "approved_at": False})
            if not self.env.su:
                values["requested_by_id"] = self.env.user.id
            if values.get("name", "New") == "New":
                values["name"] = self.env["ir.sequence"].next_by_code(
                    "chantier.material.consumption"
                ) or "New"
            if not values.get("company_id") and values.get("chantier_id"):
                values["company_id"] = self.env["project.project"].browse(
                    values["chantier_id"]
                ).company_id.id
        return super().create(values_list)

    def _workflow_write(self, values):
        return self.with_context(_elmokrif_consumption_workflow_token=_CONSUMPTION_WORKFLOW_TOKEN).write(values)

    def _is_requester_or_approver(self):
        return self.env.su or self.requested_by_id == self.env.user or self.env.user.has_group(
            "elmokrif_stock_controls.group_chantier_consumption_approver"
        )

    @api.constrains("chantier_id", "company_id")
    def _check_chantier_state_and_company(self):
        for consumption in self:
            if consumption.chantier_id.company_id != consumption.company_id:
                raise ValidationError(_("The consumption and chantier must use the same company."))
            if consumption.chantier_id.chantier_state != "in_progress":
                raise ValidationError(_("Material can only be consumed on an in-progress chantier."))

    def write(self, values):
        protected = {"chantier_id", "company_id", "operation_date", "work_type", "line_ids", "requested_by_id"}
        internal = {"state", "picking_id", "approved_by_id", "approved_at"}
        in_workflow = self.env.context.get("_elmokrif_consumption_workflow_token") is _CONSUMPTION_WORKFLOW_TOKEN
        if "requested_by_id" in values:
            raise AccessError(_("The original consumption requester cannot be changed."))
        if protected.intersection(values) and any(not item._is_requester_or_approver() for item in self):
            raise AccessError(_("Only the requester or an approver can change the draft consumption."))
        if protected.intersection(values) and any(item.state != "draft" for item in self):
            raise UserError(_("Only draft consumptions can be changed."))
        if internal.intersection(values) and not in_workflow:
            raise UserError(_("Use the consumption workflow actions to change workflow fields."))
        return super().write(values)

    def unlink(self):
        if any(item.state != "draft" for item in self):
            raise UserError(_("Only draft consumptions can be deleted."))
        return super().unlink()

    def action_submit(self):
        for consumption in self:
            if not consumption.line_ids:
                raise UserError(_("Add at least one material line before submitting consumption."))
            if consumption.state != "draft":
                raise UserError(_("Only a draft consumption can be submitted."))
            if not consumption._is_requester_or_approver():
                raise AccessError(_("Only the requester or a consumption approver can submit this consumption."))
        self._workflow_write({"state": "submitted"})
        return True

    def _ensure_approver(self):
        if not (
            self.env.su or self.env.user.has_group(
                "elmokrif_stock_controls.group_chantier_consumption_approver"
            )
        ):
            raise AccessError(_("Only a chantier consumption approver can approve consumption."))

    def action_approve_and_consume(self):
        self.check_access_rights("write")
        self.check_access_rule("write")
        self._ensure_approver()
        for consumption in self:
            if consumption.requested_by_id == self.env.user and not self.env.su:
                raise AccessError(_("The requester cannot approve their own material consumption."))
            self.env.cr.execute(
                "SELECT id FROM chantier_material_consumption WHERE id = %s FOR UPDATE",
                [consumption.id],
            )
            consumption.invalidate_recordset(["state", "picking_id"])
            if consumption.state != "submitted" or consumption.picking_id:
                raise UserError(_("This consumption has already been processed or is not submitted."))
            chantier = consumption.chantier_id
            self.env.cr.execute("SELECT id FROM project_project WHERE id = %s FOR UPDATE", [chantier.id])
            chantier.invalidate_recordset(["chantier_state"])
            if chantier.chantier_state != "in_progress":
                raise UserError(_("The chantier is no longer open for consumption."))
            moves = []
            for line in consumption.line_ids:
                available = self.env["stock.quant"]._get_available_quantity(
                    line.product_id, chantier.site_location_id, strict=False
                )
                if float_compare(
                    available, line.product_uom_qty,
                    precision_rounding=line.product_uom_id.rounding,
                ) < 0:
                    raise UserError(_(
                        "Only %(available)s %(uom)s of %(product)s is available at this site."
                    ) % {
                        "available": available, "uom": line.product_uom_id.name,
                        "product": line.product_id.display_name,
                    })
                moves.append((0, 0, {
                    "name": line.product_id.display_name,
                    "product_id": line.product_id.id,
                    "product_uom_qty": line.product_uom_qty,
                    "product_uom": line.product_uom_id.id,
                    "location_id": chantier.site_location_id.id,
                    "location_dest_id": chantier.warehouse_id.chantier_consumption_location_id.id,
                    "chantier_consumption_line_id": line.id,
                }))
            picking = self.env["stock.picking"].with_context(
                _elmokrif_consumption_workflow_token=_CONSUMPTION_WORKFLOW_TOKEN
            ).create({
                "picking_type_id": chantier.warehouse_id.int_type_id.id,
                "location_id": chantier.site_location_id.id,
                "location_dest_id": chantier.warehouse_id.chantier_consumption_location_id.id,
                "chantier_id": chantier.id,
                "chantier_operation": "consumption",
                "chantier_consumption_id": consumption.id,
                "origin": consumption.name,
                "move_ids_without_package": moves,
            })
            picking.action_confirm()
            picking.action_assign()
            if any(move.state not in ("assigned", "done") for move in picking.move_ids):
                raise UserError(_("The site stock changed before this consumption could be reserved. Please retry."))
            for move in picking.move_ids:
                move.quantity = move.product_uom_qty
                move.picked = True
            result = picking.with_context(
                _elmokrif_consumption_workflow_token=_CONSUMPTION_WORKFLOW_TOKEN,
                skip_backorder=True,
            ).button_validate()
            if isinstance(result, dict):
                raise UserError(_("The consumption could not be completed automatically."))
            consumption._workflow_write({
                "state": "done", "picking_id": picking.id,
                "approved_by_id": self.env.user.id, "approved_at": fields.Datetime.now(),
            })
        return True

    def action_cancel(self):
        if any(item.state not in ("draft", "submitted") for item in self):
            raise UserError(_("Only a draft or submitted consumption can be cancelled."))
        if any(not item._is_requester_or_approver() for item in self):
            raise AccessError(_("Only the requester or a consumption approver can cancel this consumption."))
        self._workflow_write({"state": "cancel"})
        return True


class ChantierMaterialConsumptionLine(models.Model):
    _name = "chantier.material.consumption.line"
    _description = "Chantier Material Consumption Line"
    _check_company_auto = True

    consumption_id = fields.Many2one(
        "chantier.material.consumption", required=True, ondelete="cascade"
    )
    company_id = fields.Many2one(related="consumption_id.company_id", store=True, readonly=True)
    product_id = fields.Many2one(
        "product.product", required=True, domain="[('type', '=', 'product')]"
    )
    product_uom_id = fields.Many2one(related="product_id.uom_id", readonly=True)
    product_uom_qty = fields.Float(string="Consumed Quantity", required=True, default=1.0)
    stock_move_id = fields.Many2one("stock.move", readonly=True, copy=False, ondelete="restrict")

    @api.model_create_multi
    def create(self, values_list):
        if any(values.get("stock_move_id") for values in values_list):
            raise AccessError(_("Stock movement links are managed by the consumption workflow."))
        default_consumption = self.default_get(["consumption_id"]).get("consumption_id")
        for values in values_list:
            values.setdefault("consumption_id", default_consumption)
            values["stock_move_id"] = False
        consumptions = self.env["chantier.material.consumption"].browse(
            [values.get("consumption_id") for values in values_list if values.get("consumption_id")]
        )
        if any(item.state != "draft" or not item._is_requester_or_approver() for item in consumptions):
            raise AccessError(_("Lines can only be added by the requester or an approver while consumption is draft."))
        return super().create(values_list)

    def write(self, values):
        if "consumption_id" in values:
            raise AccessError(_("A consumption line cannot be moved to another consumption."))
        in_workflow = self.env.context.get("_elmokrif_consumption_workflow_token") is _CONSUMPTION_WORKFLOW_TOKEN
        if "stock_move_id" in values and not in_workflow:
            raise AccessError(_("Stock movement links are managed by the consumption workflow."))
        if not in_workflow and any(
            line.consumption_id.state != "draft" or not line.consumption_id._is_requester_or_approver()
            for line in self
        ):
            raise AccessError(_("Only draft consumption lines can be changed by the requester or an approver."))
        return super().write(values)

    def unlink(self):
        if any(line.consumption_id.state != "draft" or not line.consumption_id._is_requester_or_approver() for line in self):
            raise AccessError(_("Only draft consumption lines can be deleted by the requester or an approver."))
        return super().unlink()

    @api.constrains("product_uom_qty")
    def _check_positive_quantity(self):
        for line in self:
            if not math.isfinite(line.product_uom_qty) or float_compare(line.product_uom_qty, 0, precision_rounding=line.product_uom_id.rounding) <= 0:
                raise ValidationError(_("Consumed quantity must be greater than zero."))

    @api.constrains("product_id")
    def _check_stockable_product(self):
        if any(line.product_id.type != "product" for line in self):
            raise ValidationError(_("Consumption requires a stockable material product."))
