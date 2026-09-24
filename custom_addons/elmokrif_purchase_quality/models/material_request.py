from odoo import _, api, fields, models
from odoo.exceptions import UserError
from odoo.tools import float_compare


class ChantierMaterialRequest(models.Model):
    _inherit = "chantier.material.request"

    required_date = fields.Date(required=True, default=fields.Date.context_today, tracking=True)
    priority = fields.Selection(
        [("0", "Normal"), ("1", "Urgent")], default="0", required=True, tracking=True
    )
    justification = fields.Text(required=True, default="Operational chantier requirement", tracking=True)
    vendor_id = fields.Many2one(
        "res.partner",
        string="Suggested Vendor",
        domain="[('supplier_rank', '>', 0)]",
        check_company=True,
    )
    purchase_order_id = fields.Many2one(
        "purchase.order", copy=False, readonly=True, check_company=True
    )
    purchase_order_count = fields.Integer(compute="_compute_purchase_order_count")
    transfer_count = fields.Integer(compute="_compute_transfer_count")

    def _compute_purchase_order_count(self):
        for request in self:
            request.purchase_order_count = 1 if request.purchase_order_id else 0

    def _compute_transfer_count(self):
        for request in self:
            # Requesters can see the aggregate count, but not the Inventory
            # transfer records themselves.
            request.transfer_count = len(request.sudo().picking_ids)

    def _create_available_stock_transfer(self, quantities):
        self.ensure_one()
        move_commands = []
        for line, quantity in quantities.items():
            if float_compare(quantity, 0, precision_rounding=line.product_uom_id.rounding) <= 0:
                continue
            move_commands.append((0, 0, {
                "name": line.product_id.display_name,
                "product_id": line.product_id.id,
                "product_uom_qty": quantity,
                "product_uom": line.product_uom_id.id,
                "location_id": self.warehouse_id.lot_stock_id.id,
                "location_dest_id": self.location_dest_id.id,
                "material_request_line_id": line.id,
            }))
        if not move_commands:
            return self.env["stock.picking"]
        picking = self.env["stock.picking"].create({
            "picking_type_id": self.warehouse_id.int_type_id.id,
            "location_id": self.warehouse_id.lot_stock_id.id,
            "location_dest_id": self.location_dest_id.id,
            "origin": self.name,
            "chantier_id": self.chantier_id.id,
            "chantier_operation": "delivery",
            "material_request_id": self.id,
            "move_ids_without_package": move_commands,
        })
        if not self.picking_id:
            self.picking_id = picking
        picking.action_confirm()
        picking.action_assign()
        return picking

    def _create_shortage_purchase_order(self, shortages):
        self.ensure_one()
        if not shortages:
            return self.env["purchase.order"]
        if not self.vendor_id:
            raise UserError(_("Select a suggested vendor before procuring the shortage."))
        lines = []
        for line, quantity in shortages.items():
            purchase_uom = line.product_id.uom_po_id
            purchase_qty = line.product_uom_id._compute_quantity(quantity, purchase_uom)
            seller = line.product_id._select_seller(
                partner_id=self.vendor_id,
                quantity=purchase_qty,
                date=self.required_date,
                uom_id=purchase_uom,
            )
            price = seller.price if seller else line.product_id.with_company(self.company_id).standard_price
            line_values = {
                "product_id": line.product_id.id,
                "name": line.product_id.display_name,
                "product_qty": purchase_qty,
                "product_uom": purchase_uom.id,
                "price_unit": price,
                "date_planned": fields.Datetime.to_datetime(self.required_date),
                "chantier_material_request_line_id": line.id,
            }
            if self.chantier_id.analytic_account_id:
                line_values["analytic_distribution"] = {
                    str(self.chantier_id.analytic_account_id.id): 100.0
                }
            lines.append((0, 0, line_values))
        order = self.env["purchase.order"].create({
            "partner_id": self.vendor_id.id,
            "company_id": self.company_id.id,
            "currency_id": self.vendor_id.property_purchase_currency_id.id or self.company_id.currency_id.id,
            "origin": self.name,
            "picking_type_id": self.warehouse_id.in_type_id.id,
            "chantier_material_request_id": self.id,
            "order_line": lines,
        })
        self.purchase_order_id = order
        return order

    def action_plan_fulfillment(self):
        self._check_manager()
        self.ensure_one()
        # A request may have been approved while the chantier was active and
        # later placed on hold.  Recheck the commitment gate at the moment the
        # transfer or purchase order is created so an already approved request
        # cannot create new stock or procurement commitments during the hold.
        self.chantier_id._ensure_chantier_accepts_commitments()
        self.env.cr.execute(
            "SELECT id FROM chantier_material_request WHERE id = %s FOR UPDATE",
            [self.id],
        )
        self.invalidate_recordset(["state", "picking_id", "purchase_order_id"])
        if self.state not in ("approved", "partially_delivered"):
            raise UserError(_("Approve the material request before planning fulfillment."))
        available_quantities = {}
        shortages = {}
        remaining_available = {}
        for line in self.line_ids:
            pending_moves = self.picking_ids.move_ids.filtered(
                lambda move: move.state not in ("done", "cancel")
                and move.material_request_line_id == line
            )
            pending_qty = sum(
                move.product_uom._compute_quantity(
                    move.product_uom_qty, line.product_uom_id
                )
                for move in pending_moves
            )
            required_qty = max(
                0.0,
                line.product_uom_qty - line.delivered_qty - pending_qty,
            )
            if line.product_id not in remaining_available:
                remaining_available[line.product_id] = (
                    self.env["stock.quant"]._get_available_quantity(
                        line.product_id,
                        self.warehouse_id.lot_stock_id,
                        strict=False,
                    )
                    if line.product_id.type == "product"
                    else 0.0
                )
            available = remaining_available[line.product_id]
            transfer_qty = max(0.0, min(available, required_qty))
            shortage_qty = max(0.0, required_qty - transfer_qty)
            available_quantities[line] = transfer_qty
            shortages[line] = shortage_qty
            remaining_available[line.product_id] = max(0.0, available - transfer_qty)
        picking = self._create_available_stock_transfer(available_quantities)
        order = self.env["purchase.order"]
        if not self.purchase_order_id:
            order = self._create_shortage_purchase_order({
                line: quantity for line, quantity in shortages.items()
                if float_compare(
                    quantity, 0, precision_rounding=line.product_uom_id.rounding
                ) > 0
            })
        if not picking and not order:
            raise UserError(_(
                "No newly available approved stock can be planned. Receive and release "
                "the outstanding purchase quantity, then run this action again."
            ))
        return {
            "type": "ir.actions.act_window",
            "name": _("Procurement Result"),
            "res_model": "purchase.order" if order else "stock.picking",
            "view_mode": "form",
            "res_id": (order or picking).id,
        }

    def action_create_transfer(self):
        return self.action_plan_fulfillment()

    def action_view_purchase_order(self):
        self.ensure_one()
        return {
            "type": "ir.actions.act_window",
            "name": _("Purchase Order"),
            "res_model": "purchase.order",
            "view_mode": "form",
            "res_id": self.purchase_order_id.id,
        }

    def action_view_transfers(self):
        self.ensure_one()
        return {
            "type": "ir.actions.act_window",
            "name": _("Request Site Transfers"),
            "res_model": "stock.picking",
            "view_mode": "tree,form",
            "domain": [("material_request_id", "=", self.id)],
            "context": {"create": False},
        }


class ChantierMaterialRequestLine(models.Model):
    _inherit = "chantier.material.request.line"

    purchase_order_line_ids = fields.One2many(
        "purchase.order.line", "chantier_material_request_line_id", string="Purchase Lines"
    )
    central_available_qty = fields.Float(
        string="Main Stock Available", compute="_compute_fulfillment_status"
    )
    reserved_qty = fields.Float(
        string="Reserved / Planned", compute="_compute_fulfillment_status"
    )
    procurement_qty = fields.Float(
        string="Procurement", compute="_compute_fulfillment_status"
    )
    outstanding_qty = fields.Float(
        string="Outstanding", compute="_compute_fulfillment_status"
    )
    suggested_fulfillment = fields.Selection(
        [
            ("fulfilled", "Fulfilled"),
            ("stock", "Main Stock"),
            ("purchase", "Purchase"),
            ("mixed", "Stock + Purchase"),
        ],
        string="Suggested Source",
        compute="_compute_fulfillment_status",
    )

    @api.depends(
        "product_id",
        "product_uom_qty",
        "delivered_qty",
        "request_id.picking_ids.move_ids.state",
        "request_id.picking_ids.move_ids.product_uom_qty",
        "request_id.purchase_order_id.state",
        "request_id.purchase_order_id.order_line.product_qty",
    )
    def _compute_fulfillment_status(self):
        for line in self:
            # Chantier requesters may read fulfillment totals without having
            # access to the underlying Inventory and Purchase documents.
            pending_moves = line.request_id.sudo().picking_ids.move_ids.filtered(
                lambda move: move.state not in ("done", "cancel")
                and move.material_request_line_id == line
            )
            line.reserved_qty = sum(
                move.product_uom._compute_quantity(
                    move.product_uom_qty, line.product_uom_id
                )
                for move in pending_moves
            )
            purchase_lines = line.sudo().purchase_order_line_ids.filtered(
                lambda purchase_line: purchase_line.order_id.state != "cancel"
            )
            line.procurement_qty = sum(
                purchase_line.product_uom._compute_quantity(
                    purchase_line.product_qty, line.product_uom_id
                )
                for purchase_line in purchase_lines
            )
            line.outstanding_qty = max(
                0.0, line.product_uom_qty - line.delivered_qty
            )
            line.central_available_qty = (
                self.env["stock.quant"].sudo()._get_available_quantity(
                    line.product_id,
                    line.request_id.warehouse_id.lot_stock_id,
                    strict=False,
                )
                if line.product_id.type == "product" and line.request_id.warehouse_id
                else 0.0
            )
            unplanned = max(
                0.0, line.outstanding_qty - line.reserved_qty
            )
            if not unplanned:
                line.suggested_fulfillment = "fulfilled"
            elif line.central_available_qty > 0 and line.central_available_qty < unplanned:
                line.suggested_fulfillment = "mixed"
            elif line.central_available_qty >= unplanned:
                line.suggested_fulfillment = "stock"
            else:
                line.suggested_fulfillment = "purchase"
