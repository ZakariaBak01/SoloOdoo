import math

from odoo import _, api, fields, models
from odoo.exceptions import AccessError, UserError, ValidationError
from odoo.tools import float_compare


class ChantierMaterialRequest(models.Model):
    _name = "chantier.material.request"
    _description = "Chantier Material Request"
    _inherit = ["mail.thread", "mail.activity.mixin"]
    _order = "id desc"
    _check_company_auto = True

    name = fields.Char(default="New", readonly=True, copy=False, tracking=True)
    company_id = fields.Many2one(
        "res.company", required=True, default=lambda self: self.env.company,
        readonly=True, index=True,
    )
    chantier_id = fields.Many2one("project.project", required=True, tracking=True, check_company=True,
        domain="[('is_chantier', '=', True), ('company_id', '=', company_id)]")
    warehouse_id = fields.Many2one(related="chantier_id.warehouse_id", store=True, readonly=True)
    location_dest_id = fields.Many2one(related="chantier_id.site_location_id", store=True, readonly=True)
    request_date = fields.Date(default=fields.Date.context_today, required=True, tracking=True)
    requested_by = fields.Many2one("res.users", default=lambda self: self.env.user, readonly=True)
    state = fields.Selection([
        ("draft", "Draft"),
        ("submitted", "Submitted"),
        ("approved", "Approved"),
        ("partially_delivered", "Partially Delivered"),
        ("done", "Delivered"),
        ("cancel", "Cancelled"),
    ], default="draft", tracking=True)
    line_ids = fields.One2many("chantier.material.request.line", "request_id", string="Materials")
    picking_id = fields.Many2one("stock.picking", copy=False, readonly=True, check_company=True)
    picking_ids = fields.One2many("stock.picking", "material_request_id", string="Warehouse Transfers")

    @api.model_create_multi
    def create(self, vals_list):
        for vals in vals_list:
            if vals.get("state", self.env.context.get("default_state", "draft")) != "draft":
                raise UserError(_("A new material request must start in Draft."))
            if not self.env.su:
                vals["requested_by"] = self.env.user.id
            # Requests created from a chantier use that chantier's company even
            # when the user has another allowed company active.  Requests opened
            # from the global menu still receive an independent company default.
            if not vals.get("company_id"):
                chantier = self.env["project.project"].browse(vals.get("chantier_id"))
                vals["company_id"] = chantier.company_id.id or self.env.company.id
            if vals.get("name", "New") == "New":
                vals["name"] = self.env["ir.sequence"].next_by_code("chantier.material.request") or "New"
        return super().create(vals_list)

    def write(self, vals):
        if "requested_by" in vals and any(request.requested_by.id != vals["requested_by"] for request in self):
            raise UserError(_("The original material requester cannot be changed."))
        if "company_id" in vals:
            raise UserError(_("The request company is set from the selected chantier."))
        if "state" in vals:
            self._validate_state_change(vals["state"])
        if any(field in vals for field in ("chantier_id", "line_ids")) and any(
            request.state != "draft" for request in self
        ):
            raise UserError(_("Only draft material requests can be changed."))
        return super().write(vals)

    def unlink(self):
        if any(request.state != "draft" for request in self):
            raise UserError(_("Only draft material requests can be deleted."))
        return super().unlink()

    @api.constrains("chantier_id", "company_id")
    def _check_chantier_company(self):
        for request in self:
            if request.chantier_id.company_id != request.company_id:
                raise ValidationError(_("The request and chantier must belong to the same company."))

    def _validate_state_change(self, target_state):
        transitions = {
            "draft": {"submitted", "cancel"},
            "submitted": {"approved", "cancel"},
            "approved": {"partially_delivered", "done"},
            "partially_delivered": {"done"},
        }
        for request in self:
            if request.state == target_state:
                continue
            if target_state not in transitions.get(request.state, set()):
                raise UserError(_("This material request state transition is not allowed."))
            if target_state == "submitted":
                if not request.line_ids:
                    raise UserError(_("Add at least one material before submitting the request."))
                request.chantier_id._ensure_chantier_accepts_commitments()
            if target_state == "approved":
                request._check_manager()
            if target_state in ("partially_delivered", "done") and not self.env.su:
                raise AccessError(_("Delivery status is set from validated warehouse transfers."))

    def _update_delivery_state(self):
        """Synchronize a request after Odoo validates one of its transfers."""
        for request in self:
            if request.state not in ("approved", "partially_delivered"):
                continue
            request.line_ids.invalidate_recordset(["delivered_qty"])
            complete = request.line_ids and all(
                float_compare(
                    line.delivered_qty,
                    line.product_uom_qty,
                    precision_rounding=line.product_uom_id.rounding,
                ) >= 0
                for line in request.line_ids
            )
            has_delivery = any(
                float_compare(
                    line.delivered_qty,
                    0,
                    precision_rounding=line.product_uom_id.rounding,
                ) > 0
                for line in request.line_ids
            )
            target_state = "done" if complete else "partially_delivered" if has_delivery else False
            if target_state and target_state != request.state:
                request.sudo().write({"state": target_state})

    def _check_manager(self):
        if not (self.env.su or self.env.user.has_group("elmokrif_chantier.group_chantier_manager")):
            raise AccessError(_("Only a chantier manager can approve material requests."))

    def action_submit(self):
        self.write({"state": "submitted"})

    def action_approve(self):
        self.filtered(lambda item: item.state == "submitted").write({"state": "approved"})

    def action_create_transfer(self):
        self._check_manager()
        for request in self.sorted("id"):
            self.env.cr.execute(
                "SELECT id FROM chantier_material_request WHERE id = %s FOR UPDATE",
                [request.id],
            )
            request.invalidate_recordset(["state", "picking_id"])
            if request.state != "approved" or request.picking_id:
                continue
            picking_type = request.warehouse_id.int_type_id
            picking = self.env["stock.picking"].create({
                "picking_type_id": picking_type.id,
                "location_id": request.warehouse_id.lot_stock_id.id,
                "location_dest_id": request.location_dest_id.id,
                "origin": request.name,
                "chantier_id": request.chantier_id.id,
                "chantier_operation": "delivery",
                "material_request_id": request.id,
                "move_ids_without_package": [(0, 0, {
                    "name": line.product_id.display_name,
                    "product_id": line.product_id.id,
                    "product_uom_qty": line.product_uom_qty,
                    "product_uom": line.product_uom_id.id,
                    "location_id": request.warehouse_id.lot_stock_id.id,
                    "location_dest_id": request.location_dest_id.id,
                    "material_request_line_id": line.id,
                }) for line in request.line_ids],
            })
            request.picking_id = picking
        self.ensure_one()
        return {
            "type": "ir.actions.act_window",
            "name": _("Warehouse Transfer"),
            "res_model": "stock.picking",
            "view_mode": "form",
            "res_id": self.picking_id.id,
        }

    def action_cancel(self):
        self.filtered(lambda item: item.state in ("draft", "submitted")).write({"state": "cancel"})


class ChantierMaterialRequestLine(models.Model):
    _name = "chantier.material.request.line"
    _description = "Chantier Material Request Line"
    _check_company_auto = True

    request_id = fields.Many2one("chantier.material.request", required=True, ondelete="cascade")
    company_id = fields.Many2one(related="request_id.company_id", store=True, readonly=True)
    product_id = fields.Many2one("product.product", required=True, domain="[('type', 'in', ['consu', 'product'])]")
    product_uom_id = fields.Many2one(related="product_id.uom_id", readonly=True)
    product_uom_qty = fields.Float(string="Requested Quantity", required=True, default=1.0)
    delivered_qty = fields.Float(compute="_compute_quantities", string="Received")
    consumed_qty = fields.Float(compute="_compute_quantities", string="Consumed")
    returned_qty = fields.Float(compute="_compute_quantities", string="Returned")
    missing_qty = fields.Float(compute="_compute_quantities", string="Missing")

    @api.constrains("product_uom_qty", "product_id")
    def _check_positive_quantity(self):
        for line in self:
            if not math.isfinite(line.product_uom_qty) or float_compare(
                line.product_uom_qty, 0, precision_rounding=line.product_uom_id.rounding
            ) <= 0:
                raise ValidationError(_("Requested quantity must be greater than zero."))

    @api.model_create_multi
    def create(self, vals_list):
        lines = super().create(vals_list)
        if any(line.request_id.state != "draft" for line in lines):
            raise UserError(_("Materials can only be added to a draft request."))
        return lines

    def write(self, vals):
        requests = self.mapped("request_id")
        if vals.get("request_id"):
            requests |= self.env["chantier.material.request"].browse(vals["request_id"])
        if any(request.state != "draft" for request in requests):
            raise UserError(_("Only draft material request lines can be changed."))
        return super().write(vals)

    def unlink(self):
        if any(line.request_id.state != "draft" for line in self):
            raise UserError(_("Only draft material request lines can be deleted."))
        return super().unlink()

    @api.depends(
        "request_id.picking_ids.move_ids.state",
        "request_id.picking_ids.move_ids.quantity",
        "request_id.picking_ids.move_ids.product_uom",
        "request_id.picking_ids.move_ids.product_id",
        "request_id.picking_ids.move_ids.material_request_line_id",
    )
    def _compute_quantities(self):
        for line in self:
            # New transfers have an exact source-line link. The second branch
            # retains readable quantities for legacy moves created before that
            # link existed; old duplicate-product lines remain inherently
            # ambiguous and should be reconciled during migration.
            moves = self.env["stock.move"].search([
                ("state", "=", "done"),
                "|",
                ("material_request_line_id", "=", line.id),
                "&",
                ("material_request_line_id", "=", False),
                ("picking_id.material_request_id", "=", line.request_id.id),
                ("product_id", "=", line.product_id.id),
            ])
            # A request owns its receipts. Consumption, returns and losses belong
            # to the chantier inventory and are intentionally not allocated here.
            line.delivered_qty = sum(
                move.product_uom._compute_quantity(move.quantity, line.product_uom_id)
                for move in moves
            )
            line.consumed_qty = 0.0
            line.returned_qty = 0.0
            line.missing_qty = 0.0
