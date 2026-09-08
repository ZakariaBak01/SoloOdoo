from odoo import _, api, fields, models
from odoo.exceptions import AccessError, UserError, ValidationError

from .workflow import QUALITY_WORKFLOW_TOKEN

_PURCHASE_APPROVAL_TOKEN = object()

class PurchaseOrder(models.Model):
    _inherit = "purchase.order"

    chantier_material_request_id = fields.Many2one(
        "chantier.material.request",
        string="Chantier Material Request",
        copy=False,
        check_company=True,
        ondelete="restrict",
    )
    chantier_id = fields.Many2one(
        "project.project",
        related="chantier_material_request_id.chantier_id",
        store=True,
        readonly=True,
    )
    chantier_selection_rationale = fields.Text(string="Vendor Selection Rationale")
    company_currency_id = fields.Many2one(
        "res.currency", string="Company Currency", related="company_id.currency_id", readonly=True
    )
    chantier_amount_untaxed_company = fields.Monetary(
        string="Untaxed Amount (Company Currency)",
        currency_field="company_currency_id",
        compute="_compute_chantier_approval",
        store=True,
    )
    chantier_approval_required = fields.Boolean(
        compute="_compute_chantier_approval",
        store=True,
    )
    chantier_approved_by_id = fields.Many2one(
        "res.users", string="Chantier Purchase Approver", copy=False, readonly=True
    )
    chantier_approved_at = fields.Datetime(copy=False, readonly=True)
    chantier_approved_amount = fields.Monetary(
        currency_field="company_currency_id", copy=False, readonly=True
    )

    @api.depends(
        "amount_untaxed", "currency_id", "company_id",
        "company_id.chantier_purchase_approval_threshold", "date_order",
        "chantier_material_request_id",
    )
    def _compute_chantier_approval(self):
        for order in self:
            amount = order.currency_id._convert(
                order.amount_untaxed,
                order.company_id.currency_id,
                order.company_id,
                fields.Date.to_date(order.date_order) or fields.Date.context_today(order),
                round=False,
            ) if order.currency_id and order.company_id else order.amount_untaxed
            order.chantier_amount_untaxed_company = amount
            order.chantier_approval_required = bool(
                order.chantier_material_request_id
                and amount >= order.company_id.chantier_purchase_approval_threshold
            )

    @api.constrains("chantier_material_request_id", "company_id")
    def _check_chantier_request_company(self):
        for order in self.filtered("chantier_material_request_id"):
            if order.chantier_material_request_id.company_id != order.company_id:
                raise ValidationError(_("The purchase order and material request must use the same company."))

    @api.model_create_multi
    def create(self, vals_list):
        evidence = {"chantier_approved_by_id", "chantier_approved_at", "chantier_approved_amount", "chantier_approval_required", "chantier_amount_untaxed_company"}
        in_workflow = self.env.context.get("_purchase_approval_token") is _PURCHASE_APPROVAL_TOKEN
        if not in_workflow and (any(evidence.intersection(values) for values in vals_list) or any("default_" + field in self.env.context for field in evidence)):
            raise AccessError(_("Chantier purchase approval evidence is managed by the approval workflow."))
        if any(values.get("chantier_material_request_id", self.env.context.get("default_chantier_material_request_id")) and values.get("state", self.env.context.get("default_state", "draft")) != "draft" for values in vals_list):
            raise AccessError(_("Create chantier purchases as draft and use the approval actions."))
        return super().create(vals_list)

    def _create_picking(self):
        return super(PurchaseOrder, self.with_context(
            _quality_workflow_token=QUALITY_WORKFLOW_TOKEN
        ))._create_picking()

    def _clear_chantier_approval(self):
        self.with_context(_purchase_approval_token=_PURCHASE_APPROVAL_TOKEN).write({
            "chantier_approved_by_id": False,
            "chantier_approved_at": False,
            "chantier_approved_amount": 0.0,
        })

    def write(self, vals):
        critical = {"partner_id", "currency_id", "company_id", "date_order", "chantier_material_request_id", "user_id", "picking_type_id", "dest_address_id"}
        in_workflow = self.env.context.get("_purchase_approval_token") is _PURCHASE_APPROVAL_TOKEN
        if "state" in vals and not in_workflow and not (vals["state"] == "sent" and all(order.state == "draft" for order in self)) and (
            vals.get("chantier_material_request_id") or self.filtered("chantier_material_request_id")
        ):
            raise AccessError(_("Use the purchase workflow actions to change chantier purchase state."))
        if vals.get("chantier_material_request_id") and any(order.state != "draft" for order in self):
            raise UserError(_("Link a material request while the purchase order is draft."))
        if {"chantier_approved_by_id", "chantier_approved_at", "chantier_approved_amount", "chantier_approval_required", "chantier_amount_untaxed_company"}.intersection(vals) and not in_workflow:
            raise AccessError(_("Chantier purchase approval evidence is managed by the approval workflow."))
        if critical.intersection(vals) and not in_workflow:
            locked = self.filtered(lambda order: order.chantier_material_request_id and order.state in ("purchase", "done"))
            if locked:
                raise UserError(_("Cancel or reset this chantier purchase order before changing critical fields."))
            pending = self.filtered(lambda order: order.chantier_approved_by_id)
            if pending:
                pending._clear_chantier_approval()
                pending.with_context(_purchase_approval_token=_PURCHASE_APPROVAL_TOKEN).write({"state": "draft"})
        return super().write(vals)

    def button_confirm(self):
        ordinary = self.browse()
        for order in self:
            if not order.chantier_material_request_id or not order.chantier_approval_required:
                ordinary |= order
                continue
            if order.state not in ("draft", "sent"):
                continue
            order.order_line._validate_analytic_distribution()
            order._add_supplier_to_product()
            order.with_context(_purchase_approval_token=_PURCHASE_APPROVAL_TOKEN).write({"state": "to approve"})
            if order.partner_id not in order.message_partner_ids:
                order.message_subscribe([order.partner_id.id])
        if ordinary:
            return super(PurchaseOrder, ordinary.with_context(
                _purchase_approval_token=_PURCHASE_APPROVAL_TOKEN
            )).button_confirm()
        return True

    def button_approve(self, force=False):
        if any(order.state not in ("draft", "sent", "to approve") for order in self.filtered("chantier_material_request_id")):
            raise UserError(_("Only a pending chantier purchase can be approved."))
        for order in self.filtered(lambda item: item.chantier_material_request_id and item.chantier_approval_required):
            if not self.env.user.has_group(
                "elmokrif_purchase_quality.group_chantier_purchase_approver"
            ):
                raise AccessError(_("Only a chantier purchase approver can approve this order."))
            if (
                order.company_id.chantier_purchase_two_person
                and self.env.user in (order.user_id | order.create_uid)
            ):
                raise UserError(_("The buyer cannot approve their own chantier purchase order."))
            order.with_context(_purchase_approval_token=_PURCHASE_APPROVAL_TOKEN).write({
                "chantier_approved_by_id": self.env.user.id,
                "chantier_approved_at": fields.Datetime.now(),
                "chantier_approved_amount": order.chantier_amount_untaxed_company,
            })
        return super(PurchaseOrder, self.with_context(
            _purchase_approval_token=_PURCHASE_APPROVAL_TOKEN
        )).button_approve(force=force)

    def button_cancel(self):
        return super(PurchaseOrder, self.with_context(
            _purchase_approval_token=_PURCHASE_APPROVAL_TOKEN
        )).button_cancel()

    def button_draft(self):
        if any(order.state != "cancel" for order in self.filtered("chantier_material_request_id")):
            raise UserError(_("Cancel the chantier purchase before resetting it to draft."))
        self.filtered("chantier_material_request_id")._clear_chantier_approval()
        return super(PurchaseOrder, self.with_context(
            _purchase_approval_token=_PURCHASE_APPROVAL_TOKEN
        )).button_draft()

    def button_done(self):
        if any(order.state != "purchase" for order in self.filtered("chantier_material_request_id")):
            raise UserError(_("Only a confirmed chantier purchase can be locked."))
        return super(PurchaseOrder, self.with_context(
            _purchase_approval_token=_PURCHASE_APPROVAL_TOKEN
        )).button_done()

    def button_unlock(self):
        if any(order.state != "done" for order in self.filtered("chantier_material_request_id")):
            raise UserError(_("Only a locked chantier purchase can be unlocked."))
        return super(PurchaseOrder, self.with_context(
            _purchase_approval_token=_PURCHASE_APPROVAL_TOKEN
        )).button_unlock()

    def _get_destination_location(self):
        self.ensure_one()
        if (
            self.chantier_material_request_id
            and self.company_id.chantier_quality_required
        ):
            warehouse = self.picking_type_id.warehouse_id
            warehouse._ensure_chantier_quality_locations()
            return warehouse.chantier_input_location_id.id
        return super()._get_destination_location()

    def _prepare_picking(self):
        values = super()._prepare_picking()
        if self.chantier_material_request_id:
            values.update({
                "chantier_purchase_request_id": self.chantier_material_request_id.id,
                "chantier_quality_required": self.company_id.chantier_quality_required,
            })
        return values


class PurchaseOrderLine(models.Model):
    _inherit = "purchase.order.line"

    chantier_material_request_line_id = fields.Many2one(
        "chantier.material.request.line",
        string="Material Request Line",
        copy=False,
        check_company=True,
        ondelete="restrict",
    )

    def _ensure_chantier_line_can_change(self):
        for line in self.filtered("order_id.chantier_material_request_id"):
            if line.order_id.state in ("purchase", "done"):
                raise UserError(_("Reset the chantier purchase order before changing products, quantities, or prices."))
            if line.order_id.chantier_approved_by_id:
                line.order_id._clear_chantier_approval()
                line.order_id.with_context(_purchase_approval_token=_PURCHASE_APPROVAL_TOKEN).write({"state": "draft"})

    @api.model_create_multi
    def create(self, vals_list):
        lines = super().create(vals_list)
        lines._ensure_chantier_line_can_change()
        return lines

    def write(self, vals):
        if {"product_id", "product_qty", "product_uom", "price_unit", "taxes_id", "discount", "order_id", "chantier_material_request_line_id"}.intersection(vals):
            self._ensure_chantier_line_can_change()
            if vals.get("order_id"):
                target = self.env["purchase.order"].browse(vals["order_id"])
                if target.chantier_material_request_id and target.state in ("purchase", "done"):
                    raise UserError(_("Lines cannot be moved into a confirmed chantier purchase."))
        return super().write(vals)

    @api.constrains("chantier_material_request_line_id", "order_id", "product_id", "product_uom")
    def _check_chantier_request_line(self):
        for line in self.filtered("chantier_material_request_line_id"):
            request_line = line.chantier_material_request_line_id
            if (
                request_line.request_id != line.order_id.chantier_material_request_id
                or request_line.product_id != line.product_id
                or request_line.product_uom_id.category_id != line.product_uom.category_id
            ):
                raise ValidationError(_("The purchase line must match the material request, product and unit category."))

    def unlink(self):
        self._ensure_chantier_line_can_change()
        return super().unlink()
