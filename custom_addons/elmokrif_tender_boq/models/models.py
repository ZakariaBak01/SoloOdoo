import hashlib
import json
import math
import uuid

from odoo import Command, _, api, fields, models
from odoo.exceptions import AccessError, UserError, ValidationError
from odoo.tools import float_compare, float_is_zero


BOQ_WORKFLOW_TOKEN = object()
TENDER_WORKFLOW_TOKEN = object()
AWARD_WORKFLOW_TOKEN = object()


def _finite(value):
    return math.isfinite(value or 0.0)


class ConstructionBOQ(models.Model):
    _name = "construction.boq"
    _description = "Construction Bill of Quantities"
    _inherit = ["mail.thread", "mail.activity.mixin"]
    _order = "chantier_id, package_code, revision_no desc, id desc"
    _check_company_auto = True

    name = fields.Char(default="New", readonly=True, copy=False, tracking=True)
    title = fields.Char(required=True, tracking=True)
    company_id = fields.Many2one(
        "res.company", required=True, default=lambda self: self.env.company,
        index=True, readonly=True,
    )
    currency_id = fields.Many2one(related="company_id.currency_id", store=True, readonly=True)
    chantier_id = fields.Many2one(
        "project.project", required=True, check_company=True, ondelete="restrict",
        domain="[('is_chantier', '=', True), ('company_id', '=', company_id)]",
        tracking=True,
    )
    purpose = fields.Selection([
        ("internal_cost", "Internal Cost Baseline"),
        ("client_contract", "Client Contract BOQ"),
        ("procurement", "Procurement BOQ"),
        ("subcontract", "Subcontract Package"),
    ], required=True, default="internal_cost", tracking=True)
    package_code = fields.Char(required=True, default="MAIN", index=True, tracking=True)
    source_estimation_id = fields.Many2one(
        "chantier.estimation", check_company=True, ondelete="restrict", copy=False,
    )
    revision_root_id = fields.Many2one(
        "construction.boq", readonly=True, copy=False, ondelete="restrict", index=True,
    )
    previous_revision_id = fields.Many2one(
        "construction.boq", readonly=True, copy=False, ondelete="restrict",
    )
    revision_no = fields.Integer(default=0, readonly=True, copy=False)
    revision_reason = fields.Text(copy=False, tracking=True)
    is_current_revision = fields.Boolean(default=False, readonly=True, copy=False, index=True)
    state = fields.Selection([
        ("draft", "Draft"),
        ("under_review", "Under Review"),
        ("changes_requested", "Changes Requested"),
        ("reviewed", "Reviewed / Pending Approval"),
        ("approved", "Approved Baseline"),
        ("issued", "Issued for Tender"),
        ("superseded", "Superseded"),
        ("cancelled", "Cancelled"),
    ], required=True, default="draft", readonly=True, copy=False, tracking=True, index=True)
    section_ids = fields.One2many("construction.boq.wbs", "boq_id", copy=False)
    line_ids = fields.One2many("construction.boq.line", "boq_id", copy=False)
    delta_ids = fields.One2many("construction.boq.revision.delta", "boq_id", copy=False)
    tender_ids = fields.One2many("construction.tender", "boq_id", copy=False)
    tender_count = fields.Integer(compute="_compute_tender_count")
    amount_internal = fields.Monetary(compute="_compute_totals", store=True)
    amount_target = fields.Monetary(compute="_compute_totals", store=True)
    amount_contract = fields.Monetary(compute="_compute_totals", store=True)
    contingency_amount = fields.Monetary(compute="_compute_totals", store=True)
    prepared_by_id = fields.Many2one(
        "res.users", default=lambda self: self.env.user, readonly=True, copy=False,
    )
    reviewed_by_id = fields.Many2one("res.users", readonly=True, copy=False)
    reviewed_at = fields.Datetime(readonly=True, copy=False)
    approved_by_id = fields.Many2one("res.users", readonly=True, copy=False)
    approved_at = fields.Datetime(readonly=True, copy=False)
    review_comment = fields.Text(copy=False, tracking=True)
    frozen_by_id = fields.Many2one("res.users", readonly=True, copy=False)
    frozen_at = fields.Datetime(readonly=True, copy=False)
    content_hash = fields.Char(readonly=True, copy=False, index=True)
    attachment_ids = fields.Many2many(
        "ir.attachment", "construction_boq_attachment_rel", "boq_id", "attachment_id",
        string="Drawings and Evidence", copy=False,
    )

    _sql_constraints = [
        ("revision_nonnegative", "CHECK(revision_no >= 0)", "Revision number cannot be negative."),
        ("boq_revision_unique", "unique(revision_root_id, revision_no)", "A BOQ revision number must be unique."),
    ]

    @api.depends(
        "line_ids.internal_amount", "line_ids.target_amount", "line_ids.contract_amount",
        "line_ids.contingency_amount",
    )
    def _compute_totals(self):
        for boq in self:
            commercial = boq.line_ids.filtered(lambda line: not line.display_type)
            boq.amount_internal = sum(commercial.mapped("internal_amount"))
            boq.amount_target = sum(commercial.mapped("target_amount"))
            boq.amount_contract = sum(commercial.mapped("contract_amount"))
            boq.contingency_amount = sum(commercial.mapped("contingency_amount"))

    def _compute_tender_count(self):
        for boq in self:
            boq.tender_count = len(boq.tender_ids)

    def action_view_tenders(self):
        self.ensure_one()
        action = self.env.ref("elmokrif_tender_boq.action_construction_tender").read()[0]
        action["domain"] = [("boq_id", "=", self.id)]
        action["context"] = {
            "default_boq_id": self.id, "default_chantier_id": self.chantier_id.id,
            "default_company_id": self.company_id.id, "default_package_code": self.package_code,
        }
        return action

    @api.model_create_multi
    def create(self, vals_list):
        if self.env.context.get("_boq_workflow_token") is not BOQ_WORKFLOW_TOKEN:
            forbidden = {
                "state", "reviewed_by_id", "reviewed_at", "approved_by_id", "approved_at",
                "frozen_by_id", "frozen_at", "content_hash", "is_current_revision",
            }
            if any(forbidden.intersection(vals) for vals in vals_list):
                raise AccessError(_("BOQ workflow evidence is managed by workflow actions."))
        records = super().create(vals_list)
        for boq in records:
            values = {}
            if not boq.revision_root_id:
                values["revision_root_id"] = boq.id
            if boq.name == "New":
                sequence = self.env["ir.sequence"].next_by_code("construction.boq") or "BOQ/%06d" % boq.id
                values["name"] = "%s/R%02d" % (sequence, boq.revision_no)
            if values:
                boq.with_context(_boq_workflow_token=BOQ_WORKFLOW_TOKEN).write(values)
        return records

    def write(self, vals):
        internal = self.env.context.get("_boq_workflow_token") is BOQ_WORKFLOW_TOKEN
        evidence = {
            "state", "reviewed_by_id", "reviewed_at", "approved_by_id", "approved_at",
            "frozen_by_id", "frozen_at", "content_hash", "is_current_revision",
            "revision_root_id", "previous_revision_id", "revision_no",
        }
        if evidence.intersection(vals) and not internal:
            raise AccessError(_("Use the BOQ workflow actions to change status or approval evidence."))
        locked_fields = {
            "title", "company_id", "chantier_id", "purpose", "package_code",
            "source_estimation_id", "section_ids", "line_ids",
        }
        if locked_fields.intersection(vals) and any(
            boq.state in ("approved", "issued", "superseded") for boq in self
        ) and not internal:
            raise UserError(_("Approved or issued BOQs are immutable. Create a new revision."))
        return super().write(vals)

    def unlink(self):
        if any(boq.state not in ("draft", "cancelled") for boq in self):
            raise UserError(_("Only draft or cancelled BOQs can be deleted."))
        return super().unlink()

    @api.constrains("chantier_id", "company_id", "source_estimation_id")
    def _check_company_links(self):
        for boq in self:
            if not boq.chantier_id.is_chantier:
                raise ValidationError(_("A formal BOQ must be linked to a chantier."))
            if boq.chantier_id.company_id != boq.company_id:
                raise ValidationError(_("The BOQ and chantier must use the same company."))
            if boq.source_estimation_id and boq.source_estimation_id.chantier_id != boq.chantier_id:
                raise ValidationError(_("The source estimate must belong to the same chantier."))

    def _require_group(self, xmlid, message):
        if not self.env.su and not self.env.user.has_group(xmlid):
            raise AccessError(message)

    def _validate_complete(self):
        for boq in self:
            lines = boq.line_ids.filtered(lambda line: not line.display_type)
            if not lines:
                raise ValidationError(_("Add at least one BOQ line before review."))
            if any(not line.section_id for line in lines):
                raise ValidationError(_("Every BOQ line must belong to a WBS section."))
            if any(float_compare(line.quantity, 0.0, precision_rounding=line.uom_id.rounding) <= 0 for line in lines):
                raise ValidationError(_("Every measurable BOQ line must have a positive quantity."))

    def action_submit_review(self):
        self._require_group("elmokrif_tender_boq.group_boq_estimator", _("Only a BOQ estimator can submit a BOQ."))
        for boq in self:
            if boq.state not in ("draft", "changes_requested"):
                raise UserError(_("Only draft or returned BOQs can be submitted."))
        self._validate_complete()
        self.with_context(_boq_workflow_token=BOQ_WORKFLOW_TOKEN).write({"state": "under_review"})
        return True

    def action_request_changes(self):
        self._require_group("elmokrif_tender_boq.group_boq_reviewer", _("Only a BOQ reviewer can request changes."))
        reason = self.env.context.get("review_comment")
        if not reason:
            raise ValidationError(_("Enter a review comment before requesting changes."))
        if any(boq.state not in ("under_review", "reviewed") for boq in self):
            raise UserError(_("Only BOQs under review or approval can be returned."))
        self.with_context(_boq_workflow_token=BOQ_WORKFLOW_TOKEN).write({
            "state": "changes_requested", "review_comment": reason,
            "reviewed_by_id": self.env.user.id, "reviewed_at": fields.Datetime.now(),
        })
        return True

    def action_complete_review(self):
        self._require_group("elmokrif_tender_boq.group_boq_reviewer", _("Only a BOQ reviewer can complete the review."))
        self._validate_complete()
        for boq in self:
            if boq.state != "under_review":
                raise UserError(_("Only BOQs under review can be marked reviewed."))
            if boq.prepared_by_id == self.env.user:
                raise UserError(_("The preparer cannot review their own BOQ."))
        self.with_context(_boq_workflow_token=BOQ_WORKFLOW_TOKEN).write({
            "state": "reviewed", "reviewed_by_id": self.env.user.id,
            "reviewed_at": fields.Datetime.now(),
        })
        return True

    def action_approve(self):
        self._require_group("elmokrif_tender_boq.group_boq_approver", _("Only a BOQ approver can approve a baseline."))
        self._validate_complete()
        for boq in self:
            if boq.state != "reviewed" or not boq.reviewed_by_id:
                raise UserError(_("Only reviewed BOQs can be approved."))
            if self.env.user in (boq.prepared_by_id | boq.reviewed_by_id):
                raise UserError(_("The preparer or reviewer cannot approve the same BOQ."))
            self.env.cr.execute(
                "SELECT id FROM construction_boq WHERE revision_root_id = %s FOR UPDATE",
                [boq.revision_root_id.id],
            )
            previous = self.search([
                ("revision_root_id", "=", boq.revision_root_id.id),
                ("is_current_revision", "=", True), ("id", "!=", boq.id),
            ])
            previous.with_context(_boq_workflow_token=BOQ_WORKFLOW_TOKEN).write({
                "state": "superseded", "is_current_revision": False,
            })
            boq._build_revision_deltas()
            now = fields.Datetime.now()
            boq.with_context(_boq_workflow_token=BOQ_WORKFLOW_TOKEN).write({
                "state": "approved", "is_current_revision": True,
                "approved_by_id": self.env.user.id, "approved_at": now,
                "frozen_by_id": self.env.user.id, "frozen_at": now,
                "content_hash": boq._snapshot_hash(),
            })
        return True

    def action_cancel(self):
        if any(boq.state not in ("draft", "changes_requested") for boq in self):
            raise UserError(_("Only draft or returned BOQs can be cancelled."))
        self.with_context(_boq_workflow_token=BOQ_WORKFLOW_TOKEN).write({"state": "cancelled"})
        return True

    def action_create_revision(self):
        self.ensure_one()
        if self.state not in ("approved", "issued", "superseded"):
            raise UserError(_("Create a revision from an approved, issued, or superseded BOQ."))
        open_revision = self.search([
            ("revision_root_id", "=", self.revision_root_id.id),
            ("state", "in", ("draft", "under_review", "changes_requested", "reviewed")),
        ], limit=1)
        if open_revision:
            raise UserError(_("An open revision already exists: %s", open_revision.display_name))
        reason = self.env.context.get("revision_reason")
        if not reason:
            raise ValidationError(_("Enter a revision reason."))
        header = self.copy_data({
            "name": "New", "state": "draft", "revision_root_id": self.revision_root_id.id,
            "previous_revision_id": self.id, "revision_no": self.revision_no + 1,
            "revision_reason": reason, "is_current_revision": False,
            "prepared_by_id": self.env.user.id, "reviewed_by_id": False,
            "reviewed_at": False, "approved_by_id": False, "approved_at": False,
            "frozen_by_id": False, "frozen_at": False, "content_hash": False,
            "section_ids": False, "line_ids": False, "delta_ids": False,
            "tender_ids": False, "attachment_ids": False,
        })[0]
        revision = self.with_context(_boq_workflow_token=BOQ_WORKFLOW_TOKEN).create(header)
        section_map = {}
        pending = self.section_ids.sorted(lambda item: (item.parent_id.id, item.sequence, item.id))
        while pending:
            copied = self.env["construction.boq.wbs"]
            for section in pending:
                if section.parent_id and section.parent_id.id not in section_map:
                    continue
                new_section = section.copy({
                    "boq_id": revision.id,
                    "parent_id": section_map.get(section.parent_id.id) if section.parent_id else False,
                })
                section_map[section.id] = new_section.id
                copied |= section
            if not copied:
                raise ValidationError(_("The WBS hierarchy contains an invalid cycle."))
            pending -= copied
        for line in self.line_ids.sorted(lambda item: (item.sequence, item.id)):
            line.copy({"boq_id": revision.id, "section_id": section_map[line.section_id.id]})
        return revision

    def action_open_revision_wizard(self):
        self.ensure_one()
        return {
            "type": "ir.actions.act_window",
            "name": _("Create BOQ Revision"),
            "res_model": "construction.boq.revision.wizard",
            "view_mode": "form",
            "target": "new",
            "context": {"default_boq_id": self.id},
        }

    def action_open_return_wizard(self):
        self.ensure_one()
        return {
            "type": "ir.actions.act_window",
            "name": _("Request BOQ Changes"),
            "res_model": "construction.boq.return.wizard",
            "view_mode": "form",
            "target": "new",
            "context": {"default_boq_id": self.id},
        }

    def _snapshot_payload(self):
        self.ensure_one()
        return {
            "chantier": self.chantier_id.id, "purpose": self.purpose,
            "package": self.package_code, "revision": self.revision_no,
            "lines": [line._snapshot_payload() for line in self.line_ids.sorted("item_code")],
        }

    def _snapshot_hash(self):
        self.ensure_one()
        payload = json.dumps(self._snapshot_payload(), sort_keys=True, separators=(",", ":"))
        return hashlib.sha256(payload.encode("utf-8")).hexdigest()

    def _build_revision_deltas(self):
        self.ensure_one()
        self.delta_ids.unlink()
        if not self.previous_revision_id:
            return
        old = {line.line_key: line for line in self.previous_revision_id.line_ids if not line.display_type}
        new = {line.line_key: line for line in self.line_ids if not line.display_type}
        values = []
        for key in sorted(set(old) | set(new)):
            before, after = old.get(key), new.get(key)
            change_type = "modified"
            if not before:
                change_type = "added"
            elif not after:
                change_type = "removed"
            elif (
                float_is_zero(before.quantity - after.quantity, precision_rounding=after.uom_id.rounding)
                and before.internal_unit_cost == after.internal_unit_cost
                and before.target_unit_rate == after.target_unit_rate
                and before.description == after.description
            ):
                continue
            values.append({
                "boq_id": self.id, "line_key": key, "change_type": change_type,
                "old_line_id": before.id if before else False,
                "new_line_id": after.id if after else False,
                "old_quantity": before.quantity if before else 0.0,
                "new_quantity": after.quantity if after else 0.0,
                "old_unit_rate": before.target_unit_rate if before else 0.0,
                "new_unit_rate": after.target_unit_rate if after else 0.0,
                "old_amount": before.target_amount if before else 0.0,
                "new_amount": after.target_amount if after else 0.0,
            })
        if values:
            self.env["construction.boq.revision.delta"].create(values)


class ConstructionBOQWBS(models.Model):
    _name = "construction.boq.wbs"
    _description = "BOQ Work Breakdown Structure"
    _parent_store = True
    _parent_name = "parent_id"
    _order = "sequence, code, id"
    _check_company_auto = True

    boq_id = fields.Many2one("construction.boq", required=True, ondelete="cascade", index=True)
    company_id = fields.Many2one(related="boq_id.company_id", store=True, readonly=True)
    parent_id = fields.Many2one("construction.boq.wbs", ondelete="restrict", index=True)
    parent_path = fields.Char(index=True, unaccent=False)
    child_ids = fields.One2many("construction.boq.wbs", "parent_id")
    sequence = fields.Integer(default=10)
    code = fields.Char(required=True)
    name = fields.Char(required=True)
    description = fields.Text()
    line_ids = fields.One2many("construction.boq.line", "section_id")
    amount_internal = fields.Monetary(compute="_compute_totals", currency_field="currency_id", recursive=True)
    amount_target = fields.Monetary(compute="_compute_totals", currency_field="currency_id", recursive=True)
    currency_id = fields.Many2one(related="boq_id.currency_id")

    _sql_constraints = [
        ("boq_wbs_code_unique", "unique(boq_id, code)", "WBS codes must be unique within a BOQ revision."),
    ]

    @api.depends("line_ids.internal_amount", "line_ids.target_amount", "child_ids.amount_internal", "child_ids.amount_target")
    def _compute_totals(self):
        for section in self:
            section.amount_internal = sum(section.line_ids.mapped("internal_amount")) + sum(section.child_ids.mapped("amount_internal"))
            section.amount_target = sum(section.line_ids.mapped("target_amount")) + sum(section.child_ids.mapped("amount_target"))

    @api.constrains("parent_id", "boq_id")
    def _check_parent(self):
        if not self._check_recursion():
            raise ValidationError(_("A WBS section cannot contain itself."))
        for section in self.filtered("parent_id"):
            if section.parent_id.boq_id != section.boq_id:
                raise ValidationError(_("A parent WBS section must belong to the same BOQ."))

    def _ensure_mutable(self):
        if any(section.boq_id.state not in ("draft", "changes_requested") for section in self):
            raise UserError(_("WBS sections can only be changed on editable BOQ revisions."))

    @api.model_create_multi
    def create(self, vals_list):
        records = super().create(vals_list)
        records._ensure_mutable()
        return records

    def write(self, vals):
        self._ensure_mutable()
        return super().write(vals)

    def unlink(self):
        self._ensure_mutable()
        return super().unlink()


class ConstructionBOQLine(models.Model):
    _name = "construction.boq.line"
    _description = "BOQ Line"
    _order = "sequence, item_code, id"
    _check_company_auto = True

    boq_id = fields.Many2one("construction.boq", required=True, ondelete="cascade", index=True)
    company_id = fields.Many2one(related="boq_id.company_id", store=True, readonly=True)
    currency_id = fields.Many2one(related="boq_id.currency_id", readonly=True)
    section_id = fields.Many2one("construction.boq.wbs", required=True, ondelete="restrict", index=True)
    sequence = fields.Integer(default=10)
    display_type = fields.Selection([("line_note", "Note")])
    item_code = fields.Char(required=True, index=True)
    line_key = fields.Char(required=True, default=lambda self: str(uuid.uuid4()), readonly=True, copy=True, index=True)
    description = fields.Text(required=True)
    product_id = fields.Many2one("product.product", check_company=True)
    cost_code_id = fields.Many2one("chantier.cost.code", check_company=True)
    uom_id = fields.Many2one("uom.uom", required=True)
    quantity_method = fields.Selection([("manual", "Manual"), ("takeoff", "Quantity Take-Off")], default="manual", required=True)
    manual_quantity = fields.Float(default=1.0)
    quantity = fields.Float(compute="_compute_quantity", store=True)
    takeoff_ids = fields.One2many("construction.boq.takeoff", "boq_line_id", copy=True)
    rate_component_ids = fields.One2many("construction.boq.rate.component", "boq_line_id", copy=True)
    provisional = fields.Boolean()
    optional = fields.Boolean()
    material_unit_cost = fields.Monetary(compute="_compute_rate", store=True)
    labor_unit_cost = fields.Monetary(compute="_compute_rate", store=True)
    equipment_unit_cost = fields.Monetary(compute="_compute_rate", store=True)
    subcontract_unit_cost = fields.Monetary(compute="_compute_rate", store=True)
    other_unit_cost = fields.Monetary(compute="_compute_rate", store=True)
    direct_unit_cost = fields.Monetary(compute="_compute_rate", store=True)
    overhead_percent = fields.Float(default=0.0)
    contingency_percent = fields.Float(default=0.0)
    overhead_amount = fields.Monetary(compute="_compute_amounts", store=True)
    contingency_amount = fields.Monetary(compute="_compute_amounts", store=True)
    internal_unit_cost = fields.Monetary(compute="_compute_amounts", store=True)
    internal_amount = fields.Monetary(compute="_compute_amounts", store=True)
    target_margin_percent = fields.Float(default=0.0)
    target_unit_rate = fields.Monetary(compute="_compute_amounts", store=True)
    target_amount = fields.Monetary(compute="_compute_amounts", store=True)
    contract_unit_rate = fields.Monetary(default=0.0)
    contract_amount = fields.Monetary(compute="_compute_amounts", store=True)
    committed_amount = fields.Monetary(compute="_compute_control_amounts")
    actual_amount = fields.Monetary(compute="_compute_control_amounts")
    cost_variance_amount = fields.Monetary(compute="_compute_control_amounts")
    tax_ids = fields.Many2many("account.tax", check_company=True)
    analytic_distribution = fields.Json()
    planned_start = fields.Date()
    planned_finish = fields.Date()

    _sql_constraints = [
        ("boq_item_code_unique", "unique(boq_id, item_code)", "BOQ item codes must be unique within a revision."),
        ("boq_line_key_unique", "unique(boq_id, line_key)", "A stable line key can occur only once in a BOQ revision."),
    ]

    @api.depends("quantity_method", "manual_quantity", "takeoff_ids.calculated_quantity")
    def _compute_quantity(self):
        for line in self:
            line.quantity = sum(line.takeoff_ids.mapped("calculated_quantity")) if line.quantity_method == "takeoff" else line.manual_quantity

    @api.depends("rate_component_ids.component_type", "rate_component_ids.amount")
    def _compute_rate(self):
        field_by_type = {
            "material": "material_unit_cost", "labour": "labor_unit_cost",
            "equipment": "equipment_unit_cost", "subcontract": "subcontract_unit_cost",
            "other": "other_unit_cost",
        }
        for line in self:
            totals = {key: 0.0 for key in field_by_type}
            for component in line.rate_component_ids:
                totals[component.component_type] += component.amount
            for component_type, field_name in field_by_type.items():
                line[field_name] = totals[component_type]
            line.direct_unit_cost = sum(totals.values())

    @api.depends("quantity", "direct_unit_cost", "overhead_percent", "contingency_percent", "target_margin_percent", "contract_unit_rate")
    def _compute_amounts(self):
        for line in self:
            line.overhead_amount = line.direct_unit_cost * line.overhead_percent / 100.0
            base = line.direct_unit_cost + line.overhead_amount
            line.contingency_amount = base * line.contingency_percent / 100.0 * line.quantity
            line.internal_unit_cost = base * (1.0 + line.contingency_percent / 100.0)
            line.internal_amount = line.quantity * line.internal_unit_cost
            margin_denominator = 1.0 - line.target_margin_percent / 100.0
            line.target_unit_rate = line.internal_unit_cost / margin_denominator if margin_denominator > 0 else 0.0
            line.target_amount = line.quantity * line.target_unit_rate
            line.contract_amount = line.quantity * line.contract_unit_rate

    def _compute_control_amounts(self):
        PurchaseLine = self.env["purchase.order.line"]
        MoveLine = self.env["account.move.line"]
        for line in self:
            purchase_lines = PurchaseLine.search([
                ("boq_line_id", "=", line.id),
                ("order_id.state", "in", ("purchase", "done")),
            ])
            committed = 0.0
            for purchase_line in purchase_lines:
                order = purchase_line.order_id
                committed += order.currency_id._convert(
                    purchase_line.price_subtotal, line.currency_id, line.company_id,
                    fields.Date.to_date(order.date_order) or fields.Date.context_today(line),
                )
            actual_lines = MoveLine.search([
                ("boq_line_id", "=", line.id), ("move_id.state", "=", "posted"),
                ("move_id.move_type", "in", ("in_invoice", "in_refund", "entry")),
                ("display_type", "not in", ("line_section", "line_note")),
            ])
            line.committed_amount = committed
            line.actual_amount = sum(actual_lines.mapped("balance"))
            line.cost_variance_amount = line.actual_amount - line.internal_amount

    @api.constrains("manual_quantity", "overhead_percent", "contingency_percent", "target_margin_percent", "contract_unit_rate")
    def _check_values(self):
        for line in self.filtered(lambda item: not item.display_type):
            values = (line.manual_quantity, line.overhead_percent, line.contingency_percent, line.target_margin_percent, line.contract_unit_rate)
            if not all(_finite(value) for value in values):
                raise ValidationError(_("BOQ quantities, rates, and percentages must be finite."))
            if line.manual_quantity < 0 or min(line.overhead_percent, line.contingency_percent, line.target_margin_percent, line.contract_unit_rate) < 0:
                raise ValidationError(_("BOQ quantities, rates, and percentages cannot be negative."))
            if line.target_margin_percent >= 100:
                raise ValidationError(_("Target margin must be less than 100%."))
            if line.planned_start and line.planned_finish and line.planned_finish < line.planned_start:
                raise ValidationError(_("The planned finish cannot precede the planned start."))
            if line.section_id.boq_id != line.boq_id:
                raise ValidationError(_("The BOQ line and WBS section must belong to the same revision."))

    def _ensure_mutable(self):
        if any(line.boq_id.state not in ("draft", "changes_requested") for line in self):
            raise UserError(_("BOQ lines can only be changed on editable revisions."))

    @api.model_create_multi
    def create(self, vals_list):
        records = super().create(vals_list)
        records._ensure_mutable()
        return records

    def write(self, vals):
        self._ensure_mutable()
        return super().write(vals)

    def unlink(self):
        self._ensure_mutable()
        return super().unlink()

    def _snapshot_payload(self):
        self.ensure_one()
        return {
            "key": self.line_key, "code": self.item_code, "description": self.description,
            "section": self.section_id.code, "uom": self.uom_id.id, "quantity": self.quantity,
            "internal_rate": self.internal_unit_cost, "target_rate": self.target_unit_rate,
            "contract_rate": self.contract_unit_rate,
            "components": [component._snapshot_payload() for component in self.rate_component_ids.sorted("sequence")],
            "takeoffs": [takeoff._snapshot_payload() for takeoff in self.takeoff_ids.sorted("sequence")],
        }


class ConstructionBOQTakeoff(models.Model):
    _name = "construction.boq.takeoff"
    _description = "BOQ Quantity Take-Off"
    _order = "sequence, id"

    boq_line_id = fields.Many2one("construction.boq.line", required=True, ondelete="cascade")
    sequence = fields.Integer(default=10)
    description = fields.Char(required=True)
    drawing_reference = fields.Char()
    drawing_revision = fields.Char()
    location = fields.Char()
    formula_type = fields.Selection([
        ("length", "Length"), ("area", "Area"), ("volume", "Volume"),
        ("count", "Count"), ("weight", "Weight"), ("manual", "Manual"),
    ], required=True, default="manual")
    length = fields.Float(default=1.0)
    width = fields.Float(default=1.0)
    height_or_depth = fields.Float(default=1.0)
    count = fields.Float(default=1.0)
    factor = fields.Float(default=1.0)
    wastage_percent = fields.Float(default=0.0)
    manual_quantity = fields.Float(default=1.0)
    calculated_quantity = fields.Float(compute="_compute_quantity", store=True)
    attachment_ids = fields.Many2many(
        "ir.attachment", "construction_boq_takeoff_attachment_rel", "takeoff_id", "attachment_id",
    )

    @api.depends("formula_type", "length", "width", "height_or_depth", "count", "factor", "wastage_percent", "manual_quantity")
    def _compute_quantity(self):
        for takeoff in self:
            bases = {
                "length": takeoff.length,
                "area": takeoff.length * takeoff.width,
                "volume": takeoff.length * takeoff.width * takeoff.height_or_depth,
                "count": takeoff.count,
                "weight": takeoff.manual_quantity,
                "manual": takeoff.manual_quantity,
            }
            takeoff.calculated_quantity = bases[takeoff.formula_type] * takeoff.factor * (1.0 + takeoff.wastage_percent / 100.0)

    @api.constrains("length", "width", "height_or_depth", "count", "factor", "wastage_percent", "manual_quantity")
    def _check_values(self):
        for takeoff in self:
            values = (takeoff.length, takeoff.width, takeoff.height_or_depth, takeoff.count, takeoff.factor, takeoff.wastage_percent, takeoff.manual_quantity)
            if not all(_finite(value) for value in values) or min(values) < 0:
                raise ValidationError(_("Take-off inputs must be finite and cannot be negative."))

    def _ensure_mutable(self):
        if any(item.boq_line_id.boq_id.state not in ("draft", "changes_requested") for item in self):
            raise UserError(_("Take-off entries can only be changed on editable BOQ revisions."))

    @api.model_create_multi
    def create(self, vals_list):
        records = super().create(vals_list)
        records._ensure_mutable()
        return records

    def write(self, vals):
        self._ensure_mutable()
        return super().write(vals)

    def unlink(self):
        self._ensure_mutable()
        return super().unlink()

    def _snapshot_payload(self):
        self.ensure_one()
        return {key: self[key] for key in (
            "description", "drawing_reference", "drawing_revision", "location", "formula_type",
            "length", "width", "height_or_depth", "count", "factor", "wastage_percent",
            "manual_quantity", "calculated_quantity",
        )}


class ConstructionBOQRateComponent(models.Model):
    _name = "construction.boq.rate.component"
    _description = "BOQ Rate Analysis Component"
    _order = "sequence, id"
    _check_company_auto = True

    boq_line_id = fields.Many2one("construction.boq.line", required=True, ondelete="cascade")
    company_id = fields.Many2one(related="boq_line_id.company_id", store=True, readonly=True)
    currency_id = fields.Many2one(related="boq_line_id.currency_id", readonly=True)
    sequence = fields.Integer(default=10)
    component_type = fields.Selection([
        ("material", "Material"), ("labour", "Labour"), ("equipment", "Equipment"),
        ("subcontract", "Subcontract"), ("other", "Other"),
    ], required=True, default="material")
    description = fields.Char(required=True)
    product_id = fields.Many2one("product.product", check_company=True)
    uom_id = fields.Many2one("uom.uom")
    quantity_per_unit = fields.Float(default=1.0, required=True)
    waste_percent = fields.Float(default=0.0)
    unit_rate = fields.Monetary(required=True)
    amount = fields.Monetary(compute="_compute_amount", store=True)
    source_estimation_id = fields.Many2one("chantier.estimation", ondelete="restrict")

    @api.depends("quantity_per_unit", "waste_percent", "unit_rate")
    def _compute_amount(self):
        for component in self:
            component.amount = component.quantity_per_unit * (1.0 + component.waste_percent / 100.0) * component.unit_rate

    @api.constrains("quantity_per_unit", "waste_percent", "unit_rate")
    def _check_values(self):
        for component in self:
            values = (component.quantity_per_unit, component.waste_percent, component.unit_rate)
            if not all(_finite(value) for value in values) or min(values) < 0:
                raise ValidationError(_("Rate-analysis quantities, waste, and rates must be finite and non-negative."))

    def _ensure_mutable(self):
        if any(item.boq_line_id.boq_id.state not in ("draft", "changes_requested") for item in self):
            raise UserError(_("Rate components can only be changed on editable BOQ revisions."))

    @api.model_create_multi
    def create(self, vals_list):
        records = super().create(vals_list)
        records._ensure_mutable()
        return records

    def write(self, vals):
        self._ensure_mutable()
        return super().write(vals)

    def unlink(self):
        self._ensure_mutable()
        return super().unlink()

    def _snapshot_payload(self):
        self.ensure_one()
        return {
            "type": self.component_type, "description": self.description,
            "product": self.product_id.id, "uom": self.uom_id.id,
            "quantity": self.quantity_per_unit, "waste": self.waste_percent,
            "rate": self.unit_rate, "amount": self.amount,
        }


class ConstructionBOQRevisionDelta(models.Model):
    _name = "construction.boq.revision.delta"
    _description = "BOQ Revision Delta"
    _order = "line_key"

    boq_id = fields.Many2one("construction.boq", required=True, ondelete="cascade", index=True)
    currency_id = fields.Many2one(related="boq_id.currency_id")
    line_key = fields.Char(required=True, index=True)
    change_type = fields.Selection([("added", "Added"), ("modified", "Modified"), ("removed", "Removed")], required=True)
    old_line_id = fields.Many2one("construction.boq.line", ondelete="set null")
    new_line_id = fields.Many2one("construction.boq.line", ondelete="set null")
    old_quantity = fields.Float(readonly=True)
    new_quantity = fields.Float(readonly=True)
    old_unit_rate = fields.Monetary(readonly=True)
    new_unit_rate = fields.Monetary(readonly=True)
    old_amount = fields.Monetary(readonly=True)
    new_amount = fields.Monetary(readonly=True)
    amount_delta = fields.Monetary(compute="_compute_delta")

    @api.depends("old_amount", "new_amount")
    def _compute_delta(self):
        for delta in self:
            delta.amount_delta = delta.new_amount - delta.old_amount


class ConstructionTender(models.Model):
    _name = "construction.tender"
    _description = "Construction Tender"
    _inherit = ["mail.thread", "mail.activity.mixin"]
    _order = "submission_deadline desc, id desc"
    _check_company_auto = True

    name = fields.Char(default="New", readonly=True, copy=False, tracking=True)
    title = fields.Char(required=True, tracking=True)
    company_id = fields.Many2one("res.company", required=True, default=lambda self: self.env.company, readonly=True)
    company_currency_id = fields.Many2one(related="company_id.currency_id", readonly=True)
    chantier_id = fields.Many2one("project.project", required=True, check_company=True, ondelete="restrict")
    boq_id = fields.Many2one("construction.boq", required=True, check_company=True, ondelete="restrict", tracking=True)
    tender_type = fields.Selection([
        ("client", "Client Tender Submission"), ("material", "Material Procurement"),
        ("subcontract", "Subcontract Package"), ("service", "Service Procurement"),
    ], required=True, default="subcontract", tracking=True)
    package_code = fields.Char(required=True)
    state = fields.Selection([
        ("draft", "Draft"), ("approved_issue", "Approved for Issue"),
        ("issued", "Issued"), ("clarification", "Clarification"),
        ("closed", "Bids Closed"), ("technical", "Technical Evaluation"),
        ("commercial", "Commercial Evaluation"), ("recommendation", "Award Recommendation"),
        ("awarded", "Awarded"), ("cancelled", "Cancelled"),
    ], default="draft", required=True, readonly=True, tracking=True, index=True)
    issue_date = fields.Date(readonly=True, copy=False)
    clarification_deadline = fields.Datetime()
    submission_deadline = fields.Datetime(required=True)
    closing_date = fields.Datetime(readonly=True, copy=False)
    buyer_id = fields.Many2one("res.users", default=lambda self: self.env.user, required=True)
    tender_manager_id = fields.Many2one("res.users", required=True)
    evaluation_committee_ids = fields.Many2many("res.users", "construction_tender_committee_rel")
    bid_ids = fields.One2many("construction.tender.bid", "tender_id", copy=False)
    criterion_ids = fields.One2many("construction.tender.criterion", "tender_id", copy=True)
    comparison_ids = fields.One2many("construction.tender.comparison", "tender_id", copy=False)
    award_ids = fields.One2many("construction.tender.award", "tender_id", copy=False)
    technical_weight = fields.Float(default=40.0)
    commercial_weight = fields.Float(default=50.0)
    delivery_weight = fields.Float(default=5.0)
    risk_weight = fields.Float(default=5.0)
    approved_for_issue_by_id = fields.Many2one("res.users", readonly=True, copy=False)
    approved_for_issue_at = fields.Datetime(readonly=True, copy=False)
    award_approved_by_id = fields.Many2one("res.users", readonly=True, copy=False)
    award_approved_at = fields.Datetime(readonly=True, copy=False)
    attachment_ids = fields.Many2many("ir.attachment", "construction_tender_attachment_rel", "tender_id", "attachment_id")

    @api.model_create_multi
    def create(self, vals_list):
        if self.env.context.get("_tender_workflow_token") is not TENDER_WORKFLOW_TOKEN:
            forbidden = {"state", "issue_date", "closing_date", "approved_for_issue_by_id", "approved_for_issue_at", "award_approved_by_id", "award_approved_at"}
            if any(forbidden.intersection(vals) for vals in vals_list):
                raise AccessError(_("Tender workflow evidence is managed by workflow actions."))
        records = super().create(vals_list)
        for tender in records.filtered(lambda item: item.name == "New"):
            name = self.env["ir.sequence"].next_by_code("construction.tender") or "TND/%06d" % tender.id
            tender.with_context(_tender_workflow_token=TENDER_WORKFLOW_TOKEN).write({"name": name})
        return records

    def write(self, vals):
        internal = self.env.context.get("_tender_workflow_token") is TENDER_WORKFLOW_TOKEN
        evidence = {"state", "issue_date", "closing_date", "approved_for_issue_by_id", "approved_for_issue_at", "award_approved_by_id", "award_approved_at"}
        if evidence.intersection(vals) and not internal:
            raise AccessError(_("Use tender workflow actions to change status or approval evidence."))
        if {"boq_id", "chantier_id", "company_id", "package_code", "tender_type"}.intersection(vals) and any(t.state != "draft" for t in self) and not internal:
            raise UserError(_("Tender scope cannot be changed after issue approval."))
        return super().write(vals)

    @api.constrains("boq_id", "chantier_id", "company_id")
    def _check_scope(self):
        for tender in self:
            if tender.boq_id.chantier_id != tender.chantier_id or tender.chantier_id.company_id != tender.company_id:
                raise ValidationError(_("Tender, BOQ, chantier, and company must match."))

    @api.constrains("technical_weight", "commercial_weight", "delivery_weight", "risk_weight")
    def _check_weights(self):
        for tender in self:
            weights = (tender.technical_weight, tender.commercial_weight, tender.delivery_weight, tender.risk_weight)
            if not all(_finite(value) and value >= 0 for value in weights) or not math.isclose(sum(weights), 100.0, abs_tol=0.01):
                raise ValidationError(_("Tender evaluation weights must be non-negative and total 100%."))

    def action_approve_issue(self):
        if not self.env.su and not self.env.user.has_group("elmokrif_tender_boq.group_tender_manager"):
            raise AccessError(_("Only a tender manager can approve a tender for issue."))
        for tender in self:
            if tender.state != "draft" or tender.boq_id.state not in ("approved", "issued"):
                raise UserError(_("Only a draft tender with an approved or previously issued BOQ can be approved for issue."))
            if not tender.criterion_ids or not tender.bid_ids:
                raise ValidationError(_("Add evaluation criteria and invited bidders before approval."))
        self.with_context(_tender_workflow_token=TENDER_WORKFLOW_TOKEN).write({
            "state": "approved_issue", "approved_for_issue_by_id": self.env.user.id,
            "approved_for_issue_at": fields.Datetime.now(),
        })
        return True

    def action_issue(self):
        self._require_group("elmokrif_tender_boq.group_tender_manager", _("Only a tender manager can issue a tender."))
        if any(tender.state != "approved_issue" for tender in self):
            raise UserError(_("Only approved tender packages can be issued."))
        now = fields.Datetime.now()
        if any(tender.submission_deadline <= now for tender in self):
            raise ValidationError(_("Submission deadline must be in the future."))
        self.with_context(_tender_workflow_token=TENDER_WORKFLOW_TOKEN).write({"state": "issued", "issue_date": fields.Date.today()})
        self.mapped("boq_id").with_context(_boq_workflow_token=BOQ_WORKFLOW_TOKEN).write({"state": "issued"})
        return True

    def action_close_bids(self):
        self._require_group("elmokrif_tender_boq.group_tender_manager", _("Only a tender manager can close bids."))
        for tender in self:
            if tender.state not in ("issued", "clarification"):
                raise UserError(_("Only an issued tender can be closed."))
            self.env.cr.execute("SELECT id FROM construction_tender WHERE id = %s FOR UPDATE", [tender.id])
            if any(bid.state not in ("submitted", "withdrawn") for bid in tender.bid_ids):
                raise ValidationError(_("Every invited bidder must submit or withdraw before closing bids."))
            tender.with_context(_tender_workflow_token=TENDER_WORKFLOW_TOKEN).write({"state": "closed", "closing_date": fields.Datetime.now()})
        return True

    def action_start_technical_evaluation(self):
        self._require_group("elmokrif_tender_boq.group_tender_manager", _("Only a tender manager can start technical evaluation."))
        if any(tender.state != "closed" for tender in self):
            raise UserError(_("Close bids before technical evaluation."))
        self.with_context(_tender_workflow_token=TENDER_WORKFLOW_TOKEN).write({"state": "technical"})
        self.mapped("bid_ids")._open_for_evaluation()
        return True

    def action_start_commercial_evaluation(self):
        self._require_group("elmokrif_tender_boq.group_tender_manager", _("Only a tender manager can start commercial evaluation."))
        for tender in self:
            if tender.state != "technical":
                raise UserError(_("Complete technical evaluation first."))
            if not tender.bid_ids.filtered(lambda bid: bid.state == "evaluated" and bid.technical_compliant):
                raise ValidationError(_("At least one technically compliant bid is required."))
        self.with_context(_tender_workflow_token=TENDER_WORKFLOW_TOKEN).write({"state": "commercial"})
        return True

    def action_build_comparison(self):
        self.ensure_one()
        self._require_group("elmokrif_tender_boq.group_tender_manager", _("Only a tender manager can freeze the commercial comparison."))
        if self.state not in ("commercial", "recommendation"):
            raise UserError(_("Bid comparison is available during commercial evaluation."))
        existing = self.env["construction.tender.comparison"].search([
            ("tender_id", "=", self.id), ("state", "=", "frozen"),
        ], order="snapshot_at desc, id desc", limit=1)
        if existing:
            return existing
        eligible = self.bid_ids.filtered(lambda bid: bid.state == "evaluated" and bid.technical_compliant and bid.completeness_percent >= 100.0)
        if not eligible:
            raise ValidationError(_("No complete, technically compliant bid is available."))
        lowest = min(eligible.mapped("normalized_total"))
        ranked = eligible.sorted(lambda bid: (bid.normalized_total, bid.id))
        for index, bid in enumerate(ranked, 1):
            commercial = lowest / bid.normalized_total * 100.0 if bid.normalized_total else 100.0
            final = (
                bid.technical_score * self.technical_weight
                + commercial * self.commercial_weight
                + bid.delivery_score * self.delivery_weight
                + bid.risk_score * self.risk_weight
            ) / 100.0
            bid.with_context(_tender_workflow_token=TENDER_WORKFLOW_TOKEN).write({
                "commercial_score": commercial, "final_score": final, "rank": index,
            })
        ranked = eligible.sorted(lambda bid: (-bid.final_score, bid.normalized_total, bid.id))
        for index, bid in enumerate(ranked, 1):
            bid.with_context(_tender_workflow_token=TENDER_WORKFLOW_TOKEN).write({"rank": index})
        comparison = self.env["construction.tender.comparison"].create({"tender_id": self.id})
        comparison.action_build_snapshot()
        return comparison

    def action_open_comparison(self):
        comparison = self.action_build_comparison()
        return {
            "type": "ir.actions.act_window",
            "name": _("Tender Comparison"),
            "res_model": "construction.tender.comparison",
            "view_mode": "form",
            "res_id": comparison.id,
            "target": "current",
        }


class ConstructionTenderCriterion(models.Model):
    _name = "construction.tender.criterion"
    _description = "Tender Evaluation Criterion"
    _order = "sequence, id"

    tender_id = fields.Many2one("construction.tender", required=True, ondelete="cascade")
    sequence = fields.Integer(default=10)
    name = fields.Char(required=True)
    category = fields.Selection([("technical", "Technical"), ("delivery", "Delivery"), ("risk", "Quality, Safety and Risk")], required=True, default="technical")
    weight = fields.Float(required=True, default=1.0)
    mandatory = fields.Boolean(default=False)
    minimum_score = fields.Float(default=0.0)

    @api.constrains("weight", "minimum_score")
    def _check_values(self):
        for criterion in self:
            if not _finite(criterion.weight) or criterion.weight <= 0 or not 0 <= criterion.minimum_score <= 100:
                raise ValidationError(_("Criterion weight must be positive and minimum score must be between 0 and 100."))


class ConstructionTenderBid(models.Model):
    _name = "construction.tender.bid"
    _description = "Tender Bid"
    _inherit = ["mail.thread", "mail.activity.mixin"]
    _order = "tender_id, bid_round desc, id"
    _check_company_auto = True

    tender_id = fields.Many2one("construction.tender", required=True, ondelete="cascade", index=True)
    company_id = fields.Many2one(related="tender_id.company_id", store=True, readonly=True)
    company_currency_id = fields.Many2one(related="tender_id.company_currency_id", string="Company Currency", readonly=True)
    partner_id = fields.Many2one("res.partner", required=True, ondelete="restrict", tracking=True)
    reference = fields.Char()
    state = fields.Selection([
        ("invited", "Invited"), ("preparation", "In Preparation"),
        ("submitted", "Submitted"), ("opened", "Opened"),
        ("clarification", "Clarification"), ("evaluated", "Evaluated"),
        ("recommended", "Recommended"), ("awarded", "Awarded"),
        ("unsuccessful", "Unsuccessful"), ("withdrawn", "Withdrawn"),
    ], default="invited", required=True, readonly=True, tracking=True)
    currency_id = fields.Many2one("res.currency", string="Bid Currency", required=True, default=lambda self: self.env.company.currency_id)
    locked_company_rate = fields.Float(readonly=True, copy=False, digits=(18, 8))
    bid_round = fields.Integer(default=1, readonly=True)
    parent_bid_id = fields.Many2one("construction.tender.bid", readonly=True, ondelete="restrict")
    line_ids = fields.One2many("construction.tender.bid.line", "bid_id", copy=True)
    score_ids = fields.One2many("construction.tender.bid.score", "bid_id", copy=True)
    submission_date = fields.Datetime(readonly=True, copy=False)
    validity_date = fields.Date()
    delivery_days = fields.Integer()
    payment_term_id = fields.Many2one("account.payment.term", check_company=True)
    retention_percent = fields.Float()
    advance_percent = fields.Float()
    warranty_months = fields.Integer()
    technical_compliant = fields.Boolean(default=False, readonly=True)
    quoted_total = fields.Monetary(compute="_compute_totals", store=True)
    normalized_total = fields.Monetary(compute="_compute_totals", store=True, currency_field="company_currency_id")
    completeness_percent = fields.Float(compute="_compute_totals", store=True)
    technical_score = fields.Float(compute="_compute_scores", store=True)
    delivery_score = fields.Float(compute="_compute_scores", store=True)
    risk_score = fields.Float(compute="_compute_scores", store=True)
    commercial_score = fields.Float(readonly=True, copy=False)
    final_score = fields.Float(readonly=True, copy=False)
    rank = fields.Integer(readonly=True, copy=False)
    deviation_notes = fields.Text()
    exclusion_notes = fields.Text()
    attachment_ids = fields.Many2many("ir.attachment", "construction_tender_bid_attachment_rel", "bid_id", "attachment_id")

    _sql_constraints = [
        ("tender_partner_round_unique", "unique(tender_id, partner_id, bid_round)", "A bidder can submit only one bid per tender round."),
    ]

    @api.model_create_multi
    def create(self, vals_list):
        if self.env.context.get("_tender_workflow_token") is not TENDER_WORKFLOW_TOKEN:
            forbidden = {"state", "submission_date", "locked_company_rate", "technical_compliant", "commercial_score", "final_score", "rank"}
            if any(forbidden.intersection(vals) for vals in vals_list):
                raise AccessError(_("Bid workflow evidence is managed by workflow actions."))
        return super().create(vals_list)

    @api.depends("line_ids.quoted_amount", "line_ids.normalized_amount", "line_ids.no_bid", "tender_id.boq_id.line_ids.internal_amount")
    def _compute_totals(self):
        for bid in self:
            bid.quoted_total = sum(bid.line_ids.mapped("quoted_amount"))
            bid.normalized_total = sum(bid.line_ids.mapped("normalized_amount"))
            required = bid.tender_id.boq_id.line_ids.filtered(lambda line: not line.display_type and not line.optional)
            priced = bid.line_ids.filtered(lambda line: not line.no_bid and line.boq_line_id in required).mapped("boq_line_id")
            denominator = sum(required.mapped("internal_amount"))
            numerator = sum(priced.mapped("internal_amount"))
            bid.completeness_percent = numerator / denominator * 100.0 if denominator else (100.0 if len(priced) == len(required) else 0.0)

    @api.depends("score_ids.score", "score_ids.criterion_id.weight", "score_ids.criterion_id.category")
    def _compute_scores(self):
        for bid in self:
            for category, field_name in (("technical", "technical_score"), ("delivery", "delivery_score"), ("risk", "risk_score")):
                scores = bid.score_ids.filtered(lambda item: item.criterion_id.category == category)
                weight = sum(scores.mapped("criterion_id.weight"))
                bid[field_name] = sum(item.score * item.criterion_id.weight for item in scores) / weight if weight else 0.0

    def _ensure_editable(self):
        if any(bid.state not in ("invited", "preparation", "clarification") for bid in self):
            raise UserError(_("Submitted or evaluated bids are immutable. Create a clarification round."))

    def action_populate_from_boq(self):
        for bid in self:
            bid._ensure_editable()
            existing_lines = set(bid.line_ids.mapped("boq_line_id").ids)
            missing_lines = bid.tender_id.boq_id.line_ids.filtered(
                lambda line: not line.display_type and line.id not in existing_lines
            )
            if missing_lines:
                self.env["construction.tender.bid.line"].create([{
                    "bid_id": bid.id, "boq_line_id": line.id,
                    "quoted_quantity": line.quantity, "uom_id": line.uom_id.id,
                } for line in missing_lines])
            if bid.state == "invited":
                bid.with_context(_tender_workflow_token=TENDER_WORKFLOW_TOKEN).write({"state": "preparation"})
        return True

    def action_submit(self):
        for bid in self:
            if bid.tender_id.state not in ("issued", "clarification") or bid.state not in ("invited", "preparation", "clarification"):
                raise UserError(_("This bid cannot be submitted in its current state."))
            if fields.Datetime.now() > bid.tender_id.submission_deadline:
                raise UserError(_("The tender submission deadline has passed."))
            baseline = bid.tender_id.boq_id.line_ids.filtered(lambda line: not line.display_type)
            required = baseline.filtered(lambda line: not line.optional)
            bid_line_ids = set(bid.line_ids.mapped("boq_line_id").ids)
            if not set(required.ids).issubset(bid_line_ids):
                raise ValidationError(_("Every mandatory BOQ line must be priced or explicitly marked No Bid."))
            if not bid_line_ids.issubset(set(baseline.ids)):
                raise ValidationError(_("Bid lines must reference the tender BOQ."))
            rate = self.env["res.currency"]._get_conversion_rate(
                bid.currency_id, bid.company_currency_id, bid.company_id,
                fields.Date.context_today(bid),
            )
            bid.with_context(_tender_workflow_token=TENDER_WORKFLOW_TOKEN).write({
                "state": "submitted", "submission_date": fields.Datetime.now(),
                "locked_company_rate": rate,
            })
            bid.line_ids._recompute_normalization()
        return True

    def _open_for_evaluation(self):
        self.filtered(lambda bid: bid.state == "submitted").with_context(_tender_workflow_token=TENDER_WORKFLOW_TOKEN).write({"state": "opened"})

    def action_complete_evaluation(self):
        for bid in self:
            if bid.tender_id.state != "technical" or bid.state != "opened":
                raise UserError(_("The bid is not open for technical evaluation."))
            mandatory_criteria = bid.tender_id.criterion_ids.filtered("mandatory")
            compliant = True
            for criterion in mandatory_criteria:
                criterion_scores = bid.score_ids.filtered(lambda item: item.criterion_id == criterion)
                average = sum(criterion_scores.mapped("score")) / len(criterion_scores) if criterion_scores else 0.0
                if not criterion_scores or average < criterion.minimum_score:
                    compliant = False
                    break
            bid.with_context(_tender_workflow_token=TENDER_WORKFLOW_TOKEN).write({"state": "evaluated", "technical_compliant": compliant})
        return True

    def action_create_clarification_round(self):
        self.ensure_one()
        if self.state not in ("opened", "evaluated"):
            raise UserError(_("Clarification is available only for an opened or evaluated bid."))
        return self.with_context(_tender_workflow_token=TENDER_WORKFLOW_TOKEN).copy({
            "state": "clarification", "bid_round": self.bid_round + 1,
            "parent_bid_id": self.id, "submission_date": False,
            "locked_company_rate": 0.0, "technical_compliant": False,
            "commercial_score": 0.0, "final_score": 0.0, "rank": 0,
        })

    def action_prepare_award(self):
        self.ensure_one()
        if self.state != "evaluated" or not self.technical_compliant:
            raise UserError(_("Only an evaluated, technically compliant bid can be recommended for award."))
        comparisons = self.env["construction.tender.comparison"].search([
            ("tender_id", "=", self.tender_id.id), ("state", "=", "frozen"),
        ], order="snapshot_at desc, id desc", limit=1)
        if not comparisons:
            raise UserError(_("Build and freeze a tender comparison before preparing an award."))
        award_lines = [Command.create({
            "bid_line_id": line.id,
            "awarded_quantity": line.boq_line_id.quantity,
            "awarded_unit_rate": line.uom_id._compute_price(
                line.quoted_unit_rate * (1.0 - line.discount_percent / 100.0),
                line.boq_line_id.uom_id,
            ),
        }) for line in self.line_ids.filtered(lambda line: not line.no_bid and line.alternative_no == 0)]
        return {
            "type": "ir.actions.act_window",
            "name": _("Prepare Award"),
            "res_model": "construction.tender.award",
            "view_mode": "form",
            "target": "current",
            "context": {
                "default_tender_id": self.tender_id.id,
                "default_comparison_id": comparisons.id,
                "default_bid_id": self.id,
                "default_line_ids": award_lines,
            },
        }

    def write(self, vals):
        internal = self.env.context.get("_tender_workflow_token") is TENDER_WORKFLOW_TOKEN
        if (
            not internal and not self.env.su
            and self.env.user.has_group("elmokrif_tender_boq.group_tender_evaluator")
            and not self.env.user.has_group("elmokrif_tender_boq.group_tender_buyer")
        ):
            raise AccessError(_("Evaluators enter scores in the Evaluation tab; bid terms are controlled by the tender buyer."))
        evidence = {"state", "submission_date", "locked_company_rate", "technical_compliant", "commercial_score", "final_score", "rank"}
        if evidence.intersection(vals) and not internal:
            raise AccessError(_("Bid workflow evidence is managed by workflow actions."))
        business = {"partner_id", "currency_id", "line_ids", "score_ids", "retention_percent", "advance_percent", "delivery_days"}
        if business.intersection(vals) and not internal:
            self._ensure_editable()
        return super().write(vals)


class ConstructionTenderBidLine(models.Model):
    _name = "construction.tender.bid.line"
    _description = "Tender Bid Line"
    _order = "boq_line_id, alternative_no, id"

    bid_id = fields.Many2one("construction.tender.bid", required=True, ondelete="cascade")
    currency_id = fields.Many2one(related="bid_id.currency_id", string="Bid Currency")
    company_currency_id = fields.Many2one(related="bid_id.company_currency_id", string="Company Currency")
    boq_line_id = fields.Many2one("construction.boq.line", required=True, ondelete="restrict")
    line_key = fields.Char(related="boq_line_id.line_key", store=True, readonly=True)
    quoted_quantity = fields.Float(required=True)
    uom_id = fields.Many2one("uom.uom", required=True)
    quoted_unit_rate = fields.Monetary()
    discount_percent = fields.Float()
    freight_amount = fields.Monetary()
    exclusion_adjustment = fields.Monetary(help="Cost assigned by the evaluator for excluded scope.")
    commercial_adjustment = fields.Monetary(help="Documented leveling adjustment in bid currency.")
    quoted_amount = fields.Monetary(compute="_compute_amounts", store=True)
    normalized_unit_rate = fields.Monetary(compute="_compute_amounts", store=True, currency_field="company_currency_id")
    normalized_amount = fields.Monetary(compute="_compute_amounts", store=True, currency_field="company_currency_id")
    variance_percent = fields.Float(compute="_compute_amounts", store=True)
    technical_compliance = fields.Selection([("compliant", "Compliant"), ("deviation", "Deviation"), ("excluded", "Excluded")], default="compliant")
    deviation_description = fields.Text()
    no_bid = fields.Boolean()
    alternative_no = fields.Integer(default=0)
    alternative_description = fields.Text()

    _sql_constraints = [
        ("bid_boq_line_alternative_unique", "unique(bid_id, boq_line_id, alternative_no)", "A bidder can quote a BOQ line only once per alternative."),
    ]

    @api.depends("quoted_quantity", "quoted_unit_rate", "discount_percent", "freight_amount", "exclusion_adjustment", "commercial_adjustment", "no_bid", "bid_id.locked_company_rate", "boq_line_id.quantity", "boq_line_id.internal_unit_cost")
    def _compute_amounts(self):
        for line in self:
            if line.no_bid:
                line.quoted_amount = line.normalized_unit_rate = line.normalized_amount = line.variance_percent = 0.0
                continue
            discounted_rate = line.quoted_unit_rate * (1.0 - line.discount_percent / 100.0)
            line.quoted_amount = line.quoted_quantity * discounted_rate
            baseline_uom_rate = line.uom_id._compute_price(discounted_rate, line.boq_line_id.uom_id)
            normalized_bid_currency = line.boq_line_id.quantity * baseline_uom_rate + line.freight_amount + line.exclusion_adjustment + line.commercial_adjustment
            rate = line.bid_id.locked_company_rate or 1.0
            line.normalized_amount = normalized_bid_currency * rate
            line.normalized_unit_rate = line.normalized_amount / line.boq_line_id.quantity if line.boq_line_id.quantity else 0.0
            baseline = line.boq_line_id.internal_unit_cost
            line.variance_percent = (line.normalized_unit_rate - baseline) / baseline * 100.0 if baseline else 0.0

    def _recompute_normalization(self):
        self._recompute_recordset(["quoted_amount", "normalized_unit_rate", "normalized_amount", "variance_percent"])

    @api.constrains("boq_line_id", "bid_id", "uom_id", "quoted_quantity", "quoted_unit_rate", "discount_percent")
    def _check_values(self):
        for line in self:
            if line.boq_line_id.boq_id != line.bid_id.tender_id.boq_id:
                raise ValidationError(_("Bid lines must reference the tender's frozen BOQ revision."))
            if line.uom_id.category_id != line.boq_line_id.uom_id.category_id:
                raise ValidationError(_("Bid and BOQ units must belong to the same UoM category."))
            values = (line.quoted_quantity, line.quoted_unit_rate, line.discount_percent, line.freight_amount, line.exclusion_adjustment, line.commercial_adjustment)
            if not all(_finite(value) for value in values) or line.quoted_quantity < 0 or line.quoted_unit_rate < 0 or not 0 <= line.discount_percent <= 100:
                raise ValidationError(_("Bid quantities and rates must be finite; discount must be between 0 and 100%."))

    def _ensure_editable(self):
        self.mapped("bid_id")._ensure_editable()

    @api.model_create_multi
    def create(self, vals_list):
        records = super().create(vals_list)
        records._ensure_editable()
        return records

    def write(self, vals):
        self._ensure_editable()
        return super().write(vals)

    def unlink(self):
        self._ensure_editable()
        return super().unlink()


class ConstructionTenderBidScore(models.Model):
    _name = "construction.tender.bid.score"
    _description = "Tender Bid Evaluation Score"

    bid_id = fields.Many2one("construction.tender.bid", required=True, ondelete="cascade")
    criterion_id = fields.Many2one("construction.tender.criterion", required=True, ondelete="restrict")
    evaluator_id = fields.Many2one("res.users", required=True, default=lambda self: self.env.user)
    score = fields.Float(required=True)
    comment = fields.Text()

    _sql_constraints = [
        ("bid_criterion_evaluator_unique", "unique(bid_id, criterion_id, evaluator_id)", "An evaluator can score a criterion only once."),
    ]

    @api.constrains("score", "criterion_id", "bid_id")
    def _check_score(self):
        for score in self:
            if not _finite(score.score) or not 0 <= score.score <= 100:
                raise ValidationError(_("Evaluation scores must be between 0 and 100."))
            if score.criterion_id.tender_id != score.bid_id.tender_id:
                raise ValidationError(_("The evaluation criterion must belong to the same tender."))

    @api.model_create_multi
    def create(self, vals_list):
        if not self.env.su:
            for values in vals_list:
                evaluator_id = values.get("evaluator_id", self.env.user.id)
                bid = self.env["construction.tender.bid"].browse(values.get("bid_id")).exists()
                if evaluator_id != self.env.user.id:
                    raise AccessError(_("You can only submit evaluation scores in your own name."))
                if not bid or self.env.user not in bid.tender_id.evaluation_committee_ids:
                    raise AccessError(_("Only assigned evaluation committee members can score this bid."))
        return super().create(vals_list)

    def write(self, vals):
        if not self.env.su and any(score.evaluator_id != self.env.user for score in self):
            raise AccessError(_("You can only change your own evaluation scores."))
        if "evaluator_id" in vals and vals["evaluator_id"] != self.env.user.id and not self.env.su:
            raise AccessError(_("Evaluation ownership cannot be reassigned."))
        return super().write(vals)

    def unlink(self):
        if not self.env.su and any(score.evaluator_id != self.env.user for score in self):
            raise AccessError(_("You can only delete your own evaluation scores."))
        return super().unlink()


class ConstructionTenderComparison(models.Model):
    _name = "construction.tender.comparison"
    _description = "Frozen Tender Comparison"
    _inherit = ["mail.thread", "mail.activity.mixin"]
    _order = "snapshot_at desc, id desc"

    name = fields.Char(default="New", readonly=True, copy=False)
    tender_id = fields.Many2one("construction.tender", required=True, ondelete="cascade", index=True)
    state = fields.Selection([("draft", "Draft"), ("frozen", "Frozen")], default="draft", readonly=True)
    snapshot_at = fields.Datetime(readonly=True, copy=False)
    snapshot_by_id = fields.Many2one("res.users", readonly=True, copy=False)
    line_ids = fields.One2many("construction.tender.comparison.line", "comparison_id", copy=False)
    content_hash = fields.Char(readonly=True, copy=False)

    @api.model_create_multi
    def create(self, vals_list):
        if self.env.context.get("_tender_workflow_token") is not TENDER_WORKFLOW_TOKEN:
            forbidden = {"state", "snapshot_at", "snapshot_by_id", "content_hash", "line_ids"}
            if any(forbidden.intersection(vals) for vals in vals_list):
                raise AccessError(_("Comparison evidence is managed by the tender workflow."))
        records = super().create(vals_list)
        for comparison in records.filtered(lambda item: item.name == "New"):
            comparison.name = _("%s Comparison %s", comparison.tender_id.name, comparison.id)
        return records

    def write(self, vals):
        internal = self.env.context.get("_tender_workflow_token") is TENDER_WORKFLOW_TOKEN
        if {"state", "snapshot_at", "snapshot_by_id", "content_hash", "line_ids"}.intersection(vals) and not internal:
            raise AccessError(_("Comparison snapshots are managed by the tender workflow."))
        if any(comparison.state == "frozen" for comparison in self) and not internal:
            raise UserError(_("A frozen tender comparison is immutable."))
        return super().write(vals)

    def unlink(self):
        if any(comparison.state == "frozen" for comparison in self):
            raise UserError(_("A frozen tender comparison cannot be deleted."))
        return super().unlink()

    def action_build_snapshot(self):
        self.ensure_one()
        if not self.env.su and not self.env.user.has_group("elmokrif_tender_boq.group_tender_manager"):
            raise AccessError(_("Only a tender manager can freeze the commercial comparison."))
        if self.tender_id.state not in ("commercial", "recommendation"):
            raise UserError(_("A comparison can only be frozen during commercial evaluation."))
        if self.state != "draft":
            raise UserError(_("A frozen comparison cannot be rebuilt."))
        values = []
        for bid in self.tender_id.bid_ids.filtered(lambda item: item.state == "evaluated"):
            values.append(Command.create({
                "bid_id": bid.id, "partner_id": bid.partner_id.id,
                "quoted_total": bid.quoted_total, "normalized_total": bid.normalized_total,
                "completeness_percent": bid.completeness_percent,
                "technical_compliant": bid.technical_compliant,
                "technical_score": bid.technical_score, "commercial_score": bid.commercial_score,
                "delivery_score": bid.delivery_score, "risk_score": bid.risk_score,
                "final_score": bid.final_score, "rank": bid.rank,
            }))
        payload = json.dumps([command[2] for command in values], sort_keys=True, default=str)
        self.with_context(_tender_workflow_token=TENDER_WORKFLOW_TOKEN).write({
            "line_ids": values, "state": "frozen", "snapshot_at": fields.Datetime.now(),
            "snapshot_by_id": self.env.user.id,
            "content_hash": hashlib.sha256(payload.encode("utf-8")).hexdigest(),
        })
        return True


class ConstructionTenderComparisonLine(models.Model):
    _name = "construction.tender.comparison.line"
    _description = "Tender Comparison Snapshot Line"
    _order = "rank, normalized_total, id"

    comparison_id = fields.Many2one("construction.tender.comparison", required=True, ondelete="cascade")
    company_currency_id = fields.Many2one(related="comparison_id.tender_id.company_currency_id", string="Company Currency")
    bid_id = fields.Many2one("construction.tender.bid", required=True, ondelete="restrict")
    partner_id = fields.Many2one("res.partner", required=True, ondelete="restrict")
    quoted_total = fields.Monetary(currency_field="bid_currency_id", readonly=True)
    bid_currency_id = fields.Many2one(related="bid_id.currency_id", string="Bid Currency")
    normalized_total = fields.Monetary(currency_field="company_currency_id", readonly=True)
    completeness_percent = fields.Float(readonly=True)
    technical_compliant = fields.Boolean(readonly=True)
    technical_score = fields.Float(readonly=True)
    commercial_score = fields.Float(readonly=True)
    delivery_score = fields.Float(readonly=True)
    risk_score = fields.Float(readonly=True)
    final_score = fields.Float(readonly=True)
    rank = fields.Integer(readonly=True)
    recommendation = fields.Boolean()
    recommendation_reason = fields.Text()

    @api.model_create_multi
    def create(self, vals_list):
        if self.env.context.get("_tender_workflow_token") is not TENDER_WORKFLOW_TOKEN:
            raise AccessError(_("Comparison lines can only be created from a tender snapshot."))
        return super().create(vals_list)

    def write(self, vals):
        if self.env.context.get("_tender_workflow_token") is not TENDER_WORKFLOW_TOKEN:
            raise AccessError(_("Frozen comparison lines cannot be changed."))
        return super().write(vals)

    def unlink(self):
        if self.env.context.get("_tender_workflow_token") is not TENDER_WORKFLOW_TOKEN:
            raise AccessError(_("Frozen comparison lines cannot be deleted."))
        return super().unlink()


class ConstructionTenderAward(models.Model):
    _name = "construction.tender.award"
    _description = "Tender Award"
    _inherit = ["mail.thread", "mail.activity.mixin"]
    _check_company_auto = True

    name = fields.Char(default="New", readonly=True, copy=False)
    tender_id = fields.Many2one("construction.tender", required=True, ondelete="restrict")
    company_id = fields.Many2one(related="tender_id.company_id", store=True, readonly=True)
    currency_id = fields.Many2one(related="bid_id.currency_id", readonly=True)
    comparison_id = fields.Many2one("construction.tender.comparison", required=True, ondelete="restrict")
    bid_id = fields.Many2one("construction.tender.bid", required=True, ondelete="restrict")
    partner_id = fields.Many2one(related="bid_id.partner_id", store=True, readonly=True)
    line_ids = fields.One2many("construction.tender.award.line", "award_id", copy=False)
    state = fields.Selection([("draft", "Draft"), ("recommended", "Recommended"), ("approved", "Approved"), ("converted", "Converted"), ("cancelled", "Cancelled")], default="draft", readonly=True, tracking=True)
    recommendation_reason = fields.Text(required=True)
    approved_by_id = fields.Many2one("res.users", readonly=True, copy=False)
    approved_at = fields.Datetime(readonly=True, copy=False)
    purchase_order_id = fields.Many2one("purchase.order", readonly=True, copy=False, ondelete="restrict")

    @api.model_create_multi
    def create(self, vals_list):
        if self.env.context.get("_award_workflow_token") is not AWARD_WORKFLOW_TOKEN:
            forbidden = {"state", "approved_by_id", "approved_at", "purchase_order_id"}
            if any(forbidden.intersection(vals) for vals in vals_list):
                raise AccessError(_("Award workflow evidence is managed by workflow actions."))
        records = super().create(vals_list)
        for award in records.filtered(lambda item: item.name == "New"):
            name = self.env["ir.sequence"].next_by_code("construction.tender.award") or "AWD/%06d" % award.id
            award.with_context(_award_workflow_token=AWARD_WORKFLOW_TOKEN).write({"name": name})
        return records

    def write(self, vals):
        internal = self.env.context.get("_award_workflow_token") is AWARD_WORKFLOW_TOKEN
        if {"state", "approved_by_id", "approved_at", "purchase_order_id"}.intersection(vals) and not internal:
            raise AccessError(_("Award evidence is managed by workflow actions."))
        return super().write(vals)

    @api.constrains("tender_id", "comparison_id", "bid_id")
    def _check_links(self):
        for award in self:
            if award.comparison_id.tender_id != award.tender_id or award.bid_id.tender_id != award.tender_id:
                raise ValidationError(_("Award, comparison, and bid must belong to the same tender."))
            if award.comparison_id.state != "frozen":
                raise ValidationError(_("Awards require a frozen tender comparison."))

    def action_recommend(self):
        if any(award.state != "draft" or not award.line_ids for award in self):
            raise UserError(_("A draft award requires at least one awarded line."))
        self.with_context(_award_workflow_token=AWARD_WORKFLOW_TOKEN).write({"state": "recommended"})
        self.mapped("tender_id").with_context(_tender_workflow_token=TENDER_WORKFLOW_TOKEN).write({"state": "recommendation"})
        return True

    def action_approve(self):
        if not self.env.su and not self.env.user.has_group("elmokrif_tender_boq.group_tender_award_approver"):
            raise AccessError(_("Only a tender award approver can approve an award."))
        for award in self:
            if award.state != "recommended":
                raise UserError(_("Only recommended awards can be approved."))
            if award.bid_id.tender_id.buyer_id == self.env.user:
                raise UserError(_("The tender buyer cannot approve their own award."))
        self.with_context(_award_workflow_token=AWARD_WORKFLOW_TOKEN).write({
            "state": "approved", "approved_by_id": self.env.user.id, "approved_at": fields.Datetime.now(),
        })
        return True

    def action_create_purchase_order(self):
        self.ensure_one()
        if self.purchase_order_id:
            return self.purchase_order_id
        if not self.env.su and not self.env.user.has_group("elmokrif_tender_boq.group_tender_buyer"):
            raise AccessError(_("Only an authorized tender buyer can convert an approved award."))
        if self.state != "approved":
            raise UserError(_("Approve the award before creating a purchase order."))
        if self.tender_id.tender_type not in ("material", "subcontract", "service"):
            raise UserError(_("This tender type does not create a purchase order."))
        missing = self.line_ids.filtered(lambda item: not item.boq_line_id.product_id)
        if missing:
            raise ValidationError(_("Set a procurement product on every awarded BOQ line before conversion."))
        order = self.env["purchase.order"].create({
            "partner_id": self.partner_id.id, "company_id": self.company_id.id,
            "currency_id": self.currency_id.id, "origin": self.name,
            "tender_award_id": self.id,
            "order_line": [Command.create(line._prepare_purchase_line()) for line in self.line_ids],
        })
        self.with_context(_award_workflow_token=AWARD_WORKFLOW_TOKEN).write({"state": "converted", "purchase_order_id": order.id})
        self.bid_id.with_context(_tender_workflow_token=TENDER_WORKFLOW_TOKEN).write({"state": "awarded"})
        self.tender_id.with_context(_tender_workflow_token=TENDER_WORKFLOW_TOKEN).write({
            "state": "awarded", "award_approved_by_id": self.approved_by_id.id,
            "award_approved_at": self.approved_at,
        })
        return order

    def action_open_purchase_order(self):
        order = self.action_create_purchase_order()
        return {
            "type": "ir.actions.act_window",
            "name": _("Purchase Order"),
            "res_model": "purchase.order",
            "view_mode": "form",
            "res_id": order.id,
            "target": "current",
        }


class ConstructionTenderAwardLine(models.Model):
    _name = "construction.tender.award.line"
    _description = "Tender Award Line"

    award_id = fields.Many2one("construction.tender.award", required=True, ondelete="cascade")
    bid_line_id = fields.Many2one("construction.tender.bid.line", required=True, ondelete="restrict")
    boq_line_id = fields.Many2one(related="bid_line_id.boq_line_id", store=True, readonly=True)
    currency_id = fields.Many2one(related="award_id.currency_id")
    awarded_quantity = fields.Float(required=True)
    awarded_unit_rate = fields.Monetary(required=True)
    awarded_amount = fields.Monetary(compute="_compute_amount", store=True)

    @api.depends("awarded_quantity", "awarded_unit_rate")
    def _compute_amount(self):
        for line in self:
            line.awarded_amount = line.awarded_quantity * line.awarded_unit_rate

    @api.constrains("bid_line_id", "award_id", "awarded_quantity", "awarded_unit_rate")
    def _check_values(self):
        for line in self:
            if line.bid_line_id.bid_id != line.award_id.bid_id:
                raise ValidationError(_("Award lines must come from the selected bid."))
            if not _finite(line.awarded_quantity) or not _finite(line.awarded_unit_rate) or line.awarded_quantity <= 0 or line.awarded_unit_rate < 0:
                raise ValidationError(_("Awarded quantity must be positive and the rate must be non-negative."))

    def _ensure_editable(self):
        if any(line.award_id.state == "converted" for line in self):
            raise UserError(_("Converted award lines are immutable."))

    @api.model_create_multi
    def create(self, vals_list):
        records = super().create(vals_list)
        records._ensure_editable()
        return records

    def write(self, vals):
        self._ensure_editable()
        return super().write(vals)

    def unlink(self):
        self._ensure_editable()
        return super().unlink()

    def _prepare_purchase_line(self):
        self.ensure_one()
        boq_line = self.boq_line_id
        return {
            "product_id": boq_line.product_id.id, "name": boq_line.description,
            "product_qty": self.awarded_quantity, "product_uom": boq_line.uom_id.id,
            "price_unit": self.awarded_unit_rate,
            "date_planned": fields.Datetime.now(), "boq_line_id": boq_line.id,
            "tender_bid_line_id": self.bid_line_id.id,
            "cost_code_id": boq_line.cost_code_id.id,
            "analytic_distribution": boq_line.analytic_distribution,
        }


class PurchaseOrder(models.Model):
    _inherit = "purchase.order"

    tender_award_id = fields.Many2one("construction.tender.award", copy=False, readonly=True, ondelete="restrict", check_company=True)
    tender_id = fields.Many2one(related="tender_award_id.tender_id", store=True, readonly=True)
    boq_id = fields.Many2one(related="tender_id.boq_id", store=True, readonly=True)


class PurchaseOrderLine(models.Model):
    _inherit = "purchase.order.line"

    boq_line_id = fields.Many2one("construction.boq.line", copy=False, readonly=True, ondelete="restrict", check_company=True)
    tender_bid_line_id = fields.Many2one("construction.tender.bid.line", copy=False, readonly=True, ondelete="restrict")

    def _prepare_account_move_line(self, move=False):
        values = super()._prepare_account_move_line(move=move)
        if self.boq_line_id:
            values.update({
                "boq_line_id": self.boq_line_id.id,
                "cost_code_id": self.boq_line_id.cost_code_id.id,
                "analytic_distribution": self.boq_line_id.analytic_distribution,
            })
        return values

    def _prepare_stock_moves(self, picking):
        values_list = super()._prepare_stock_moves(picking)
        if self.boq_line_id:
            for values in values_list:
                values.update({
                    "boq_line_id": self.boq_line_id.id,
                    "cost_code_id": self.boq_line_id.cost_code_id.id,
                })
        return values_list


class AccountMoveLine(models.Model):
    _inherit = "account.move.line"

    boq_line_id = fields.Many2one("construction.boq.line", copy=False, ondelete="restrict", check_company=True, index=True)


class StockMove(models.Model):
    _inherit = "stock.move"

    boq_line_id = fields.Many2one("construction.boq.line", copy=False, ondelete="restrict", check_company=True, index=True)


class SaleOrderLine(models.Model):
    _inherit = "sale.order.line"

    boq_line_id = fields.Many2one("construction.boq.line", copy=True, ondelete="restrict", check_company=True, index=True)

    def _prepare_invoice_line(self, **optional_values):
        values = super()._prepare_invoice_line(**optional_values)
        if self.boq_line_id:
            values.update({
                "boq_line_id": self.boq_line_id.id,
                "cost_code_id": self.boq_line_id.cost_code_id.id,
                "analytic_distribution": self.boq_line_id.analytic_distribution,
            })
        return values


class ChantierEstimation(models.Model):
    _inherit = "chantier.estimation"

    boq_ids = fields.One2many("construction.boq", "source_estimation_id", readonly=True)
    boq_count = fields.Integer(compute="_compute_boq_count")

    def _compute_boq_count(self):
        for estimate in self:
            estimate.boq_count = len(estimate.boq_ids)

    def action_create_boq(self):
        self.ensure_one()
        if self.state != "approved":
            raise UserError(_("Approve the estimate before generating a formal BOQ."))
        volume_uom = self.env.ref("uom.product_uom_cubic_meter", raise_if_not_found=False)
        if not volume_uom:
            raise UserError(_("Configure a cubic-metre unit of measure before generating the BOQ."))
        boq = self.env["construction.boq"].create({
            "title": self.name, "company_id": self.company_id.id,
            "chantier_id": self.chantier_id.id, "source_estimation_id": self.id,
            "purpose": "internal_cost", "package_code": "EST",
        })
        section = self.env["construction.boq.wbs"].create({
            "boq_id": boq.id, "code": "EST", "name": _("Estimate Scope"),
        })
        quantity = self.adjusted_volume or self.net_volume
        if quantity <= 0:
            raise ValidationError(_("The approved estimate must have a positive calculated volume."))
        line = self.env["construction.boq.line"].create({
            "boq_id": boq.id, "section_id": section.id, "item_code": "EST-001",
            "description": self.name, "uom_id": volume_uom.id,
            "quantity_method": "manual", "manual_quantity": quantity,
        })
        components = [
            ("material", _("Cement"), self.cement_bags / quantity, self.cement_bag_cost),
            ("material", _("Sand"), self.sand_volume / quantity, self.sand_cost_m3),
            ("material", _("Gravel"), self.gravel_volume / quantity, self.gravel_cost_m3),
            ("material", _("Water"), self.water_litres / quantity, self.water_cost_litre),
            ("labour", _("Labour"), self.labor_hours / quantity, self.labor_hourly_cost),
            ("equipment", _("Machinery"), self.team_days / quantity, self.machinery_daily_cost),
            ("other", _("Transport"), self.truck_trips / quantity, self.truck_trip_cost),
        ]
        self.env["construction.boq.rate.component"].create([{
            "boq_line_id": line.id, "component_type": component_type,
            "description": description, "quantity_per_unit": component_quantity,
            "unit_rate": rate, "source_estimation_id": self.id,
        } for component_type, description, component_quantity, rate in components if component_quantity or rate])
        return boq

    def action_generate_boq_ui(self):
        boq = self.action_create_boq()
        return {
            "type": "ir.actions.act_window", "name": _("Bill of Quantities"),
            "res_model": "construction.boq", "view_mode": "form",
            "res_id": boq.id, "target": "current",
        }

    def action_view_boqs(self):
        self.ensure_one()
        action = self.env.ref("elmokrif_tender_boq.action_construction_boq").read()[0]
        action["domain"] = [("source_estimation_id", "=", self.id)]
        action["context"] = {"default_source_estimation_id": self.id, "default_chantier_id": self.chantier_id.id}
        return action


class ProjectProject(models.Model):
    _inherit = "project.project"

    boq_ids = fields.One2many("construction.boq", "chantier_id")
    tender_ids = fields.One2many("construction.tender", "chantier_id")
    boq_count = fields.Integer(compute="_compute_tender_boq_counts")
    tender_count = fields.Integer(compute="_compute_tender_boq_counts")

    def _compute_tender_boq_counts(self):
        for chantier in self:
            chantier.boq_count = len(chantier.boq_ids)
            chantier.tender_count = len(chantier.tender_ids)

    def action_view_boqs(self):
        self.ensure_one()
        action = self.env.ref("elmokrif_tender_boq.action_construction_boq").read()[0]
        action["domain"] = [("chantier_id", "=", self.id)]
        action["context"] = {"default_chantier_id": self.id, "default_company_id": self.company_id.id}
        return action

    def action_view_tenders(self):
        self.ensure_one()
        action = self.env.ref("elmokrif_tender_boq.action_construction_tender").read()[0]
        action["domain"] = [("chantier_id", "=", self.id)]
        action["context"] = {"default_chantier_id": self.id, "default_company_id": self.company_id.id}
        return action

    def _compute_chantier_control(self):
        super()._compute_chantier_control()
        BOQ = self.env["construction.boq"]
        for chantier in self:
            baselines = BOQ.search([
                ("chantier_id", "=", chantier.id),
                ("purpose", "=", "internal_cost"),
                ("is_current_revision", "=", True),
                ("state", "in", ("approved", "issued")),
            ])
            if baselines:
                chantier.approved_budget_live = sum(baselines.mapped("amount_internal"))
                chantier.margin_forecast_live = chantier.revenue_invoiced_live - chantier.actual_cost_live
