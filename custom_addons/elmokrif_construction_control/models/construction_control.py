import math

from odoo import Command, _, api, fields, models
from odoo.exceptions import AccessError, UserError, ValidationError
from odoo.tools import float_compare


WORKFLOW_TOKEN = object()


def _finite(*values):
    return all(math.isfinite(value or 0.0) for value in values)


class ConstructionSiteIssue(models.Model):
    _name = "construction.site.issue"
    _description = "Construction Site Issue"
    _inherit = ["mail.thread", "mail.activity.mixin"]
    _order = "severity desc, due_date, id desc"
    _check_company_auto = True

    name = fields.Char(default="New", readonly=True, copy=False, tracking=True)
    title = fields.Char(required=True, tracking=True)
    chantier_id = fields.Many2one(
        "project.project", required=True, check_company=True, ondelete="restrict",
        domain="[('is_chantier', '=', True), ('company_id', '=', company_id)]", tracking=True,
    )
    company_id = fields.Many2one(
        "res.company", required=True, default=lambda self: self.env.company,
        readonly=True, index=True,
    )
    category = fields.Selection([
        ("design", "Design"), ("quality", "Quality"), ("safety", "Safety"),
        ("commercial", "Commercial"), ("programme", "Programme"),
        ("material", "Material"), ("other", "Other"),
    ], required=True, default="other", tracking=True)
    severity = fields.Selection([
        ("low", "Low"), ("medium", "Medium"), ("high", "High"),
        ("critical", "Critical"),
    ], required=True, default="medium", tracking=True)
    description = fields.Text(required=True)
    location = fields.Char()
    raised_by_id = fields.Many2one("res.users", default=lambda self: self.env.user, readonly=True)
    responsible_id = fields.Many2one("res.users", required=True, tracking=True)
    due_date = fields.Date(required=True, tracking=True)
    resolution = fields.Text(tracking=True)
    state = fields.Selection([
        ("open", "Open"), ("assigned", "Assigned"), ("resolved", "Resolved"),
        ("verified", "Verified"), ("closed", "Closed"), ("cancelled", "Cancelled"),
    ], default="open", required=True, readonly=True, tracking=True, index=True)
    attachment_ids = fields.Many2many(
        "ir.attachment", "construction_site_issue_attachment_rel", "issue_id", "attachment_id",
        string="Photos and Evidence",
    )
    rfi_ids = fields.One2many("construction.rfi", "issue_id", readonly=True)
    change_event_ids = fields.One2many("construction.change.event", "issue_id", readonly=True)

    @api.model_create_multi
    def create(self, vals_list):
        records = super().create(vals_list)
        for record in records.filtered(lambda item: item.name == "New"):
            record.name = self.env["ir.sequence"].with_company(record.company_id).next_by_code(
                "construction.site.issue"
            ) or "ISS/%06d" % record.id
        records.mapped("chantier_id")._refresh_chantier_health()
        return records

    def write(self, vals):
        if "state" in vals and self.env.context.get("_construction_workflow_token") is not WORKFLOW_TOKEN:
            raise AccessError(_("Use the issue workflow actions to change its status."))
        projects = self.mapped("chantier_id")
        result = super().write(vals)
        projects._refresh_chantier_health()
        return result

    def unlink(self):
        if any(record.state not in ("open", "cancelled") for record in self):
            raise UserError(_("Only open or cancelled issues can be deleted."))
        projects = self.mapped("chantier_id")
        result = super().unlink()
        projects._refresh_chantier_health()
        return result

    def action_assign(self):
        if any(not issue.responsible_id or issue.state != "open" for issue in self):
            raise UserError(_("Only an open issue with a responsible person can be assigned."))
        self.with_context(_construction_workflow_token=WORKFLOW_TOKEN).write({"state": "assigned"})
        return True

    def action_resolve(self):
        if any(issue.state != "assigned" or not issue.resolution for issue in self):
            raise UserError(_("Enter the resolution before resolving an assigned issue."))
        if not self.env.su and any(
            issue.responsible_id != self.env.user for issue in self
        ) and not self.env.user.has_group("elmokrif_construction_control.group_construction_control_manager"):
            raise AccessError(_("Only the responsible user or a construction control manager can resolve this issue."))
        self.with_context(_construction_workflow_token=WORKFLOW_TOKEN).write({"state": "resolved"})
        return True

    def action_verify(self):
        self._require_manager()
        if any(issue.state != "resolved" for issue in self):
            raise UserError(_("Only resolved issues can be verified."))
        self.with_context(_construction_workflow_token=WORKFLOW_TOKEN).write({"state": "verified"})
        return True

    def action_close(self):
        if any(issue.state != "verified" for issue in self):
            raise UserError(_("Verify the resolution before closing the issue."))
        self.with_context(_construction_workflow_token=WORKFLOW_TOKEN).write({"state": "closed"})
        return True

    def action_create_rfi(self):
        self.ensure_one()
        rfi = self.env["construction.rfi"].create({
            "title": self.title,
            "chantier_id": self.chantier_id.id,
            "company_id": self.company_id.id,
            "issue_id": self.id,
            "question": self.description,
            "priority": "critical" if self.severity == "critical" else self.severity,
            "responsible_id": self.responsible_id.id,
            "response_due": self.due_date,
        })
        return rfi._form_action()

    def action_create_change_event(self):
        self.ensure_one()
        reason_by_category = {
            "design": "design", "commercial": "client", "programme": "delay",
            "quality": "error", "safety": "other", "material": "other", "other": "other",
        }
        event = self.env["construction.change.event"].create({
            "title": self.title,
            "chantier_id": self.chantier_id.id,
            "company_id": self.company_id.id,
            "issue_id": self.id,
            "description": self.description,
            "reason": reason_by_category[self.category],
        })
        return event._form_action()

    def _require_manager(self):
        if not self.env.su and not self.env.user.has_group(
            "elmokrif_construction_control.group_construction_control_manager"
        ):
            raise AccessError(_("Only a construction control manager can perform this action."))


class ConstructionRFI(models.Model):
    _name = "construction.rfi"
    _description = "Construction Request for Information"
    _inherit = ["mail.thread", "mail.activity.mixin"]
    _order = "response_due, id desc"
    _check_company_auto = True

    name = fields.Char(default="New", readonly=True, copy=False, tracking=True)
    title = fields.Char(required=True, tracking=True)
    chantier_id = fields.Many2one(
        "project.project", required=True, check_company=True, ondelete="restrict",
        domain="[('is_chantier', '=', True), ('company_id', '=', company_id)]", tracking=True,
    )
    company_id = fields.Many2one("res.company", required=True, default=lambda self: self.env.company, readonly=True)
    issue_id = fields.Many2one("construction.site.issue", check_company=True, ondelete="restrict")
    boq_line_id = fields.Many2one(
        "construction.boq.line", check_company=True, ondelete="restrict",
        domain="[('boq_id.chantier_id', '=', chantier_id)]",
    )
    raised_by_id = fields.Many2one("res.users", default=lambda self: self.env.user, readonly=True)
    responsible_id = fields.Many2one("res.users", required=True, tracking=True)
    question = fields.Text(required=True, tracking=True)
    answer = fields.Text(tracking=True)
    priority = fields.Selection([
        ("low", "Low"), ("medium", "Medium"), ("high", "High"), ("critical", "Critical"),
    ], required=True, default="medium", tracking=True)
    response_due = fields.Date(required=True, tracking=True)
    submitted_at = fields.Datetime(readonly=True, copy=False)
    answered_at = fields.Datetime(readonly=True, copy=False)
    closed_at = fields.Datetime(readonly=True, copy=False)
    cost_impact = fields.Monetary(currency_field="currency_id", tracking=True)
    schedule_impact_days = fields.Integer(tracking=True)
    currency_id = fields.Many2one(related="company_id.currency_id", readonly=True)
    state = fields.Selection([
        ("draft", "Draft"), ("submitted", "Submitted"), ("under_review", "Under Review"),
        ("answered", "Answered"), ("closed", "Closed"), ("cancelled", "Cancelled"),
    ], default="draft", required=True, readonly=True, tracking=True, index=True)
    attachment_ids = fields.Many2many(
        "ir.attachment", "construction_rfi_attachment_rel", "rfi_id", "attachment_id",
        string="References and Evidence",
    )
    change_event_ids = fields.One2many("construction.change.event", "rfi_id", readonly=True)
    is_overdue = fields.Boolean(compute="_compute_overdue", search="_search_overdue")

    @api.depends("response_due", "state")
    def _compute_overdue(self):
        today = fields.Date.context_today(self)
        for record in self:
            record.is_overdue = bool(
                record.response_due and record.response_due < today
                and record.state in ("submitted", "under_review")
            )

    def _search_overdue(self, operator, value):
        positive = (operator == "=" and value) or (operator == "!=" and not value)
        domain = [("response_due", "<", fields.Date.context_today(self)), ("state", "in", ("submitted", "under_review"))]
        return domain if positive else [
            "|", "|", ("response_due", "=", False),
            ("response_due", ">=", fields.Date.context_today(self)),
            ("state", "not in", ("submitted", "under_review")),
        ]

    @api.model_create_multi
    def create(self, vals_list):
        records = super().create(vals_list)
        for record in records.filtered(lambda item: item.name == "New"):
            record.name = self.env["ir.sequence"].with_company(record.company_id).next_by_code(
                "construction.rfi"
            ) or "RFI/%06d" % record.id
        return records

    def write(self, vals):
        protected = {"state", "submitted_at", "answered_at", "closed_at"}
        if protected.intersection(vals) and self.env.context.get("_construction_workflow_token") is not WORKFLOW_TOKEN:
            raise AccessError(_("RFI status and audit evidence are controlled by workflow actions."))
        return super().write(vals)

    def action_submit(self):
        if any(record.state != "draft" for record in self):
            raise UserError(_("Only draft RFIs can be submitted."))
        self.with_context(_construction_workflow_token=WORKFLOW_TOKEN).write({
            "state": "submitted", "submitted_at": fields.Datetime.now(),
        })
        return True

    def action_review(self):
        if any(record.state != "submitted" for record in self):
            raise UserError(_("Only submitted RFIs can enter review."))
        self._ensure_responsible()
        self.with_context(_construction_workflow_token=WORKFLOW_TOKEN).write({"state": "under_review"})
        return True

    def action_answer(self):
        if any(record.state != "under_review" or not record.answer for record in self):
            raise UserError(_("Enter an answer before marking an RFI answered."))
        self._ensure_responsible()
        self.with_context(_construction_workflow_token=WORKFLOW_TOKEN).write({
            "state": "answered", "answered_at": fields.Datetime.now(),
        })
        return True

    def action_close(self):
        if any(record.state != "answered" for record in self):
            raise UserError(_("Only answered RFIs can be closed."))
        self.with_context(_construction_workflow_token=WORKFLOW_TOKEN).write({
            "state": "closed", "closed_at": fields.Datetime.now(),
        })
        return True

    def action_create_change_event(self):
        self.ensure_one()
        existing = self.change_event_ids.filtered(lambda item: item.state != "cancelled")[:1]
        if existing:
            return existing._form_action()
        event = self.env["construction.change.event"].create({
            "title": self.title, "chantier_id": self.chantier_id.id,
            "company_id": self.company_id.id, "rfi_id": self.id,
            "issue_id": self.issue_id.id, "boq_line_id": self.boq_line_id.id,
            "description": self.answer or self.question,
            "reason": "design",
            "estimated_cost_impact": self.cost_impact,
            "estimated_schedule_days": self.schedule_impact_days,
        })
        return event._form_action()

    def _form_action(self):
        self.ensure_one()
        return {"type": "ir.actions.act_window", "res_model": self._name, "res_id": self.id,
                "view_mode": "form", "target": "current"}

    def _ensure_responsible(self):
        if self.env.su or self.env.user.has_group("elmokrif_construction_control.group_construction_control_manager"):
            return
        if any(record.responsible_id != self.env.user for record in self):
            raise AccessError(_("Only the responsible user or a construction control manager can review and answer this RFI."))


class ConstructionSubmittal(models.Model):
    _name = "construction.submittal"
    _description = "Construction Submittal"
    _inherit = ["mail.thread", "mail.activity.mixin"]
    _order = "review_due, id desc"
    _check_company_auto = True

    name = fields.Char(default="New", readonly=True, copy=False, tracking=True)
    title = fields.Char(required=True, tracking=True)
    chantier_id = fields.Many2one(
        "project.project", required=True, check_company=True, ondelete="restrict",
        domain="[('is_chantier', '=', True), ('company_id', '=', company_id)]", tracking=True,
    )
    company_id = fields.Many2one("res.company", required=True, default=lambda self: self.env.company, readonly=True)
    submittal_type = fields.Selection([
        ("shop_drawing", "Shop Drawing"), ("material", "Material"),
        ("method_statement", "Method Statement"), ("sample", "Sample"),
        ("technical_data", "Technical Data"), ("other", "Other"),
    ], required=True, default="material", tracking=True)
    specification_reference = fields.Char(tracking=True)
    boq_line_id = fields.Many2one(
        "construction.boq.line", check_company=True, ondelete="restrict",
        domain="[('boq_id.chantier_id', '=', chantier_id)]",
    )
    submitted_by_partner_id = fields.Many2one("res.partner", required=True, tracking=True)
    reviewer_id = fields.Many2one("res.users", required=True, tracking=True)
    review_due = fields.Date(required=True, tracking=True)
    revision = fields.Char(default="0", required=True, tracking=True)
    description = fields.Text(required=True)
    review_comment = fields.Text(tracking=True)
    state = fields.Selection([
        ("draft", "Draft"), ("submitted", "Submitted"), ("under_review", "Under Review"),
        ("approved", "Approved"), ("approved_noted", "Approved as Noted"),
        ("rejected", "Rejected / Revise"), ("superseded", "Superseded"),
        ("cancelled", "Cancelled"),
    ], default="draft", required=True, readonly=True, tracking=True, index=True)
    decision_by_id = fields.Many2one("res.users", readonly=True, copy=False)
    decision_at = fields.Datetime(readonly=True, copy=False)
    attachment_ids = fields.Many2many(
        "ir.attachment", "construction_submittal_attachment_rel", "submittal_id", "attachment_id",
        string="Submission Files",
    )

    @api.model_create_multi
    def create(self, vals_list):
        records = super().create(vals_list)
        for record in records.filtered(lambda item: item.name == "New"):
            record.name = self.env["ir.sequence"].with_company(record.company_id).next_by_code(
                "construction.submittal"
            ) or "SUB/%06d" % record.id
        return records

    def write(self, vals):
        protected = {"state", "decision_by_id", "decision_at"}
        if protected.intersection(vals) and self.env.context.get("_construction_workflow_token") is not WORKFLOW_TOKEN:
            raise AccessError(_("Submittal decisions are controlled by workflow actions."))
        if any(record.state in ("approved", "approved_noted", "superseded") for record in self) and not self.env.context.get("_construction_workflow_token") is WORKFLOW_TOKEN:
            immutable = set(vals) - {"message_follower_ids", "message_partner_ids"}
            if immutable:
                raise UserError(_("An approved submittal is immutable. Create a revision."))
        return super().write(vals)

    def action_submit(self):
        if any(record.state not in ("draft", "rejected") or not record.attachment_ids for record in self):
            raise UserError(_("A draft or rejected submittal requires at least one submission file."))
        self.with_context(_construction_workflow_token=WORKFLOW_TOKEN).write({"state": "submitted"})
        return True

    def action_review(self):
        if any(record.state != "submitted" for record in self):
            raise UserError(_("Only submitted submittals can enter review."))
        self.with_context(_construction_workflow_token=WORKFLOW_TOKEN).write({"state": "under_review"})
        return True

    def _decision(self, state):
        if any(record.state != "under_review" or not record.review_comment for record in self):
            raise UserError(_("Enter the review comment before recording a decision."))
        if not self.env.su and any(record.reviewer_id != self.env.user for record in self) and not self.env.user.has_group("elmokrif_construction_control.group_construction_control_manager"):
            raise AccessError(_("Only the assigned reviewer or a construction control manager can decide this submittal."))
        self.with_context(_construction_workflow_token=WORKFLOW_TOKEN).write({
            "state": state, "decision_by_id": self.env.user.id, "decision_at": fields.Datetime.now(),
        })
        return True

    def action_approve(self):
        return self._decision("approved")

    def action_approve_noted(self):
        return self._decision("approved_noted")

    def action_reject(self):
        return self._decision("rejected")

    def action_create_revision(self):
        self.ensure_one()
        if self.state not in ("approved", "approved_noted", "rejected"):
            raise UserError(_("Create revisions only from decided submittals."))
        copy = self.copy({
            "name": "New", "state": "draft", "revision": str(int(self.revision) + 1) if self.revision.isdigit() else self.revision + ".1",
            "review_comment": False, "decision_by_id": False, "decision_at": False,
        })
        if self.state in ("approved", "approved_noted"):
            self.with_context(_construction_workflow_token=WORKFLOW_TOKEN).write({"state": "superseded"})
        return {"type": "ir.actions.act_window", "res_model": self._name, "res_id": copy.id,
                "view_mode": "form", "target": "current"}


class ConstructionWorkPackage(models.Model):
    _name = "construction.work.package"
    _description = "Construction Work Package"
    _inherit = ["mail.thread", "mail.activity.mixin"]
    _order = "planned_start, sequence, id"
    _check_company_auto = True

    sequence = fields.Integer(default=10)
    name = fields.Char(default="New", readonly=True, copy=False, tracking=True)
    title = fields.Char(required=True, tracking=True)
    chantier_id = fields.Many2one(
        "project.project", required=True, check_company=True, ondelete="restrict",
        domain="[('is_chantier', '=', True), ('company_id', '=', company_id)]", tracking=True,
    )
    company_id = fields.Many2one("res.company", required=True, default=lambda self: self.env.company, readonly=True)
    currency_id = fields.Many2one(related="company_id.currency_id", readonly=True)
    boq_id = fields.Many2one(
        "construction.boq", check_company=True, ondelete="restrict",
        domain="[('chantier_id', '=', chantier_id), ('is_current_revision', '=', True)]",
    )
    wbs_id = fields.Many2one(
        "construction.boq.wbs", ondelete="restrict",
        domain="[('boq_id', '=', boq_id)]",
    )
    boq_line_ids = fields.Many2many(
        "construction.boq.line", "construction_work_package_boq_line_rel",
        "package_id", "boq_line_id", string="BOQ Scope",
        domain="[('boq_id', '=', boq_id), ('section_id', 'child_of', wbs_id)]",
    )
    manager_id = fields.Many2one("res.users", required=True, tracking=True)
    responsible_id = fields.Many2one("res.users", required=True, tracking=True)
    contractor_id = fields.Many2one("res.partner", tracking=True)
    planned_start = fields.Date(required=True, tracking=True)
    planned_finish = fields.Date(required=True, tracking=True)
    actual_start = fields.Date(readonly=True, copy=False)
    actual_finish = fields.Date(readonly=True, copy=False)
    unit = fields.Char(default="unit", required=True)
    planned_quantity = fields.Float(required=True, default=1.0, tracking=True)
    installed_quantity = fields.Float(default=0.0, tracking=True)
    progress_percent = fields.Float(compute="_compute_progress", store=True)
    budget_material = fields.Monetary(tracking=True)
    budget_labour = fields.Monetary(tracking=True)
    budget_equipment = fields.Monetary(tracking=True)
    budget_subcontract = fields.Monetary(tracking=True)
    budget_total = fields.Monetary(compute="_compute_budget", store=True)
    planned_labor_hours = fields.Float(tracking=True)
    method_statement_ready = fields.Boolean(tracking=True)
    drawings_ready = fields.Boolean(tracking=True)
    permits_ready = fields.Boolean(tracking=True)
    materials_ready = fields.Boolean(tracking=True)
    inspection_required = fields.Boolean(default=True, tracking=True)
    hold_reason = fields.Text(tracking=True)
    state = fields.Selection([
        ("draft", "Draft"), ("ready", "Ready for Work"), ("released", "Released"),
        ("in_progress", "In Progress"), ("on_hold", "On Hold"),
        ("inspection", "Awaiting Inspection"), ("accepted", "Accepted"),
        ("closed", "Closed"), ("cancelled", "Cancelled"),
    ], default="draft", required=True, readonly=True, tracking=True, index=True)
    dependency_ids = fields.Many2many(
        "construction.work.package", "construction_work_package_dependency_rel",
        "package_id", "dependency_id", string="Predecessors",
    )
    task_ids = fields.One2many("project.task", "work_package_id", readonly=True)
    task_count = fields.Integer(compute="_compute_task_count")
    attachment_ids = fields.Many2many(
        "ir.attachment", "construction_work_package_attachment_rel", "package_id", "attachment_id",
        string="Method, Drawings, Permits and Evidence",
    )

    @api.depends("planned_quantity", "installed_quantity")
    def _compute_progress(self):
        for record in self:
            record.progress_percent = min(100.0, record.installed_quantity * 100.0 / record.planned_quantity) if record.planned_quantity else 0.0

    @api.depends("budget_material", "budget_labour", "budget_equipment", "budget_subcontract")
    def _compute_budget(self):
        for record in self:
            record.budget_total = record.budget_material + record.budget_labour + record.budget_equipment + record.budget_subcontract

    def _compute_task_count(self):
        for record in self:
            record.task_count = len(record.task_ids)

    @api.model_create_multi
    def create(self, vals_list):
        records = super().create(vals_list)
        for record in records.filtered(lambda item: item.name == "New"):
            record.name = self.env["ir.sequence"].with_company(record.company_id).next_by_code(
                "construction.work.package"
            ) or "WP/%06d" % record.id
        records.mapped("chantier_id")._refresh_chantier_health()
        return records

    def write(self, vals):
        protected = {"state", "actual_start", "actual_finish"}
        if protected.intersection(vals) and self.env.context.get("_construction_workflow_token") is not WORKFLOW_TOKEN:
            raise AccessError(_("Work-package status and actual dates are controlled by workflow actions."))
        projects = self.mapped("chantier_id")
        result = super().write(vals)
        projects._refresh_chantier_health()
        return result

    @api.constrains("planned_start", "planned_finish", "planned_quantity", "installed_quantity")
    def _check_values(self):
        for record in self:
            if record.planned_finish < record.planned_start:
                raise ValidationError(_("The planned finish cannot precede the planned start."))
            if not _finite(record.planned_quantity, record.installed_quantity) or record.planned_quantity <= 0 or record.installed_quantity < 0:
                raise ValidationError(_("Planned quantity must be positive and installed quantity cannot be negative."))
            if float_compare(record.installed_quantity, record.planned_quantity, precision_digits=3) > 0:
                raise ValidationError(_("Installed quantity cannot exceed the planned work-package quantity."))
            if record in record.dependency_ids or any(record in item.dependency_ids for item in record.dependency_ids):
                raise ValidationError(_("Work-package dependencies cannot contain a direct cycle."))
            if record.boq_id and record.boq_id.chantier_id != record.chantier_id:
                raise ValidationError(_("The BOQ must belong to the selected chantier."))
            if record.wbs_id and record.wbs_id.boq_id != record.boq_id:
                raise ValidationError(_("The WBS section must belong to the selected BOQ."))

    def action_mark_ready(self):
        self._require_package_manager()
        missing = []
        for record in self:
            if record.state != "draft":
                raise UserError(_("Only draft work packages can be made ready."))
            if not record.method_statement_ready:
                missing.append(_("method statement"))
            if not record.drawings_ready:
                missing.append(_("approved drawings"))
            if not record.permits_ready:
                missing.append(_("permits"))
            if not record.materials_ready:
                missing.append(_("materials"))
        if missing:
            raise UserError(_("Complete work readiness first: %s", ", ".join(sorted(set(missing)))))
        self.with_context(_construction_workflow_token=WORKFLOW_TOKEN).write({"state": "ready"})
        return True

    def action_release(self):
        self._require_package_manager()
        if any(record.state != "ready" or any(dep.state != "closed" for dep in record.dependency_ids) for record in self):
            raise UserError(_("Only ready work packages with closed predecessors can be released."))
        self.with_context(_construction_workflow_token=WORKFLOW_TOKEN).write({"state": "released"})
        return True

    def action_start(self):
        if any(record.state not in ("released", "on_hold") for record in self):
            raise UserError(_("Only released or held work packages can start."))
        self.with_context(_construction_workflow_token=WORKFLOW_TOKEN).write({
            "state": "in_progress", "actual_start": fields.Date.context_today(self), "hold_reason": False,
        })
        return True

    def action_hold(self):
        if any(record.state != "in_progress" or not record.hold_reason for record in self):
            raise UserError(_("Enter a hold reason before placing active work on hold."))
        self.with_context(_construction_workflow_token=WORKFLOW_TOKEN).write({"state": "on_hold"})
        return True

    def action_submit_inspection(self):
        if any(record.state != "in_progress" or record.progress_percent < 100 for record in self):
            raise UserError(_("Complete the planned quantity before submitting the work package."))
        for record in self:
            target = "inspection" if record.inspection_required else "accepted"
            record.with_context(_construction_workflow_token=WORKFLOW_TOKEN).write({"state": target})
        return True

    def action_accept(self):
        self._require_package_manager()
        if any(record.state != "inspection" for record in self):
            raise UserError(_("Only work awaiting inspection can be accepted."))
        self.with_context(_construction_workflow_token=WORKFLOW_TOKEN).write({"state": "accepted"})
        return True

    def _require_package_manager(self):
        if self.env.su or self.env.user.has_group("elmokrif_construction_control.group_construction_control_manager"):
            return
        if any(record.manager_id != self.env.user for record in self):
            raise AccessError(_("Only the work-package manager or a construction control manager can perform this action."))

    def action_close(self):
        if any(record.state != "accepted" for record in self):
            raise UserError(_("Only accepted work packages can be closed."))
        self.with_context(_construction_workflow_token=WORKFLOW_TOKEN).write({
            "state": "closed", "actual_finish": fields.Date.context_today(self),
        })
        return True

    def action_view_tasks(self):
        self.ensure_one()
        return {"type": "ir.actions.act_window", "name": _("Work Package Tasks"),
                "res_model": "project.task", "view_mode": "kanban,tree,form",
                "domain": [("work_package_id", "=", self.id)],
                "context": {"default_project_id": self.chantier_id.id, "default_work_package_id": self.id,
                            "default_chantier_bundle": self.title}}


class ConstructionChangeEvent(models.Model):
    _name = "construction.change.event"
    _description = "Construction Change Event"
    _inherit = ["mail.thread", "mail.activity.mixin"]
    _order = "event_date desc, id desc"
    _check_company_auto = True

    name = fields.Char(default="New", readonly=True, copy=False, tracking=True)
    title = fields.Char(required=True, tracking=True)
    chantier_id = fields.Many2one(
        "project.project", required=True, check_company=True, ondelete="restrict",
        domain="[('is_chantier', '=', True), ('company_id', '=', company_id)]", tracking=True,
    )
    company_id = fields.Many2one("res.company", required=True, default=lambda self: self.env.company, readonly=True)
    currency_id = fields.Many2one(related="company_id.currency_id", readonly=True)
    event_date = fields.Date(required=True, default=fields.Date.context_today, tracking=True)
    reason = fields.Selection([
        ("client", "Client Instruction"), ("design", "Design Change"),
        ("site_condition", "Unforeseen Site Condition"), ("quantity", "Quantity Difference"),
        ("regulatory", "Regulatory"), ("delay", "Delay / Disruption"),
        ("error", "Error / Omission"), ("other", "Other"),
    ], required=True, tracking=True)
    description = fields.Text(required=True)
    issue_id = fields.Many2one("construction.site.issue", check_company=True, ondelete="restrict")
    rfi_id = fields.Many2one("construction.rfi", check_company=True, ondelete="restrict")
    boq_line_id = fields.Many2one(
        "construction.boq.line", check_company=True, ondelete="restrict",
        domain="[('boq_id.chantier_id', '=', chantier_id)]",
    )
    raised_by_id = fields.Many2one("res.users", default=lambda self: self.env.user, readonly=True)
    owner_id = fields.Many2one("res.users", required=True, default=lambda self: self.env.user, tracking=True)
    estimated_cost_impact = fields.Monetary(tracking=True)
    estimated_revenue_impact = fields.Monetary(tracking=True)
    estimated_schedule_days = fields.Integer(tracking=True)
    responsibility = fields.Selection([
        ("client", "Client"), ("consultant", "Consultant"), ("main_contractor", "Main Contractor"),
        ("subcontractor", "Subcontractor"), ("supplier", "Supplier"), ("unknown", "To Determine"),
    ], required=True, default="unknown", tracking=True)
    state = fields.Selection([
        ("draft", "Draft"), ("submitted", "Submitted"), ("estimating", "Estimating"),
        ("review", "Commercial Review"), ("accepted", "Accepted for Variation"),
        ("converted", "Variation Created"), ("rejected", "Rejected"), ("cancelled", "Cancelled"),
    ], default="draft", required=True, readonly=True, tracking=True, index=True)
    decision_reason = fields.Text(tracking=True)
    attachment_ids = fields.Many2many(
        "ir.attachment", "construction_change_event_attachment_rel", "event_id", "attachment_id",
        string="Instruction and Evidence",
    )
    variation_order_id = fields.Many2one("construction.variation.order", readonly=True, copy=False)

    @api.model_create_multi
    def create(self, vals_list):
        records = super().create(vals_list)
        for record in records.filtered(lambda item: item.name == "New"):
            record.name = self.env["ir.sequence"].with_company(record.company_id).next_by_code(
                "construction.change.event"
            ) or "CE/%06d" % record.id
        records.mapped("chantier_id")._refresh_chantier_health()
        return records

    def write(self, vals):
        protected = {"state", "variation_order_id"}
        if protected.intersection(vals) and self.env.context.get("_construction_workflow_token") is not WORKFLOW_TOKEN:
            raise AccessError(_("Change-event status and conversion are controlled by workflow actions."))
        projects = self.mapped("chantier_id")
        result = super().write(vals)
        projects._refresh_chantier_health()
        return result

    def action_submit(self):
        if any(record.state != "draft" or not record.attachment_ids for record in self):
            raise UserError(_("Add instruction or evidence before submitting a draft change event."))
        self.with_context(_construction_workflow_token=WORKFLOW_TOKEN).write({"state": "submitted"})
        return True

    def action_estimate(self):
        if any(record.state != "submitted" for record in self):
            raise UserError(_("Only submitted change events can enter estimating."))
        self.with_context(_construction_workflow_token=WORKFLOW_TOKEN).write({"state": "estimating"})
        return True

    def action_review(self):
        if any(record.state != "estimating" for record in self):
            raise UserError(_("Only estimated change events can enter commercial review."))
        self.with_context(_construction_workflow_token=WORKFLOW_TOKEN).write({"state": "review"})
        return True

    def action_accept(self):
        if any(record.state != "review" for record in self):
            raise UserError(_("Only reviewed change events can be accepted."))
        self.with_context(_construction_workflow_token=WORKFLOW_TOKEN).write({"state": "accepted"})
        return True

    def action_reject(self):
        if any(record.state not in ("submitted", "estimating", "review") or not record.decision_reason for record in self):
            raise UserError(_("Enter a decision reason before rejecting the change event."))
        self.with_context(_construction_workflow_token=WORKFLOW_TOKEN).write({"state": "rejected"})
        return True

    def action_create_variation(self):
        self.ensure_one()
        if self.variation_order_id:
            return self.variation_order_id._form_action()
        if self.state != "accepted":
            raise UserError(_("Accept the change event before creating a variation order."))
        line_values = []
        if self.boq_line_id or self.estimated_cost_impact or self.estimated_revenue_impact:
            line_values.append(Command.create({
                "boq_line_id": self.boq_line_id.id,
                "description": self.title,
                "cost_amount": self.estimated_cost_impact,
                "revenue_amount": self.estimated_revenue_impact,
            }))
        variation = self.env["construction.variation.order"].create({
            "title": self.title, "chantier_id": self.chantier_id.id,
            "company_id": self.company_id.id, "change_event_ids": [Command.link(self.id)],
            "reason": self.description, "schedule_impact_days": self.estimated_schedule_days,
            "line_ids": line_values,
        })
        self.with_context(_construction_workflow_token=WORKFLOW_TOKEN).write({
            "variation_order_id": variation.id, "state": "converted",
        })
        return variation._form_action()

    def _form_action(self):
        self.ensure_one()
        return {"type": "ir.actions.act_window", "res_model": self._name, "res_id": self.id,
                "view_mode": "form", "target": "current"}


class ConstructionVariationOrder(models.Model):
    _name = "construction.variation.order"
    _description = "Construction Variation Order"
    _inherit = ["mail.thread", "mail.activity.mixin"]
    _order = "id desc"
    _check_company_auto = True

    name = fields.Char(default="New", readonly=True, copy=False, tracking=True)
    title = fields.Char(required=True, tracking=True)
    chantier_id = fields.Many2one(
        "project.project", required=True, check_company=True, ondelete="restrict",
        domain="[('is_chantier', '=', True), ('company_id', '=', company_id)]", tracking=True,
    )
    company_id = fields.Many2one("res.company", required=True, default=lambda self: self.env.company, readonly=True)
    currency_id = fields.Many2one(related="company_id.currency_id", readonly=True)
    customer_id = fields.Many2one(related="chantier_id.partner_id", store=True, readonly=True)
    change_event_ids = fields.Many2many(
        "construction.change.event", "construction_variation_change_event_rel",
        "variation_id", "event_id", string="Change Events",
        domain="[('chantier_id', '=', chantier_id), ('state', '=', 'accepted')]",
    )
    baseline_boq_id = fields.Many2one(
        "construction.boq", check_company=True, ondelete="restrict",
        domain="[('chantier_id', '=', chantier_id), ('is_current_revision', '=', True), ('state', 'in', ['approved', 'issued'])]",
    )
    revised_boq_id = fields.Many2one("construction.boq", readonly=True, copy=False, ondelete="restrict")
    reason = fields.Text(required=True, tracking=True)
    contractual_reference = fields.Char(tracking=True)
    schedule_impact_days = fields.Integer(tracking=True)
    line_ids = fields.One2many("construction.variation.order.line", "variation_id", copy=True)
    cost_amount = fields.Monetary(compute="_compute_amounts", store=True)
    revenue_amount = fields.Monetary(compute="_compute_amounts", store=True)
    margin_amount = fields.Monetary(compute="_compute_amounts", store=True)
    customer_approval_reference = fields.Char(copy=False, tracking=True)
    customer_approved_at = fields.Datetime(copy=False, readonly=True)
    submitted_by_id = fields.Many2one("res.users", readonly=True, copy=False)
    submitted_at = fields.Datetime(readonly=True, copy=False)
    approved_by_id = fields.Many2one("res.users", readonly=True, copy=False)
    approved_at = fields.Datetime(readonly=True, copy=False)
    state = fields.Selection([
        ("draft", "Draft"), ("submitted", "Internal Review"),
        ("customer", "Customer Approval"), ("approved", "Approved"),
        ("implemented", "Implemented"), ("rejected", "Rejected"),
        ("cancelled", "Cancelled"),
    ], default="draft", required=True, readonly=True, tracking=True, index=True)
    attachment_ids = fields.Many2many(
        "ir.attachment", "construction_variation_attachment_rel", "variation_id", "attachment_id",
        string="Signed Instructions and Evidence",
    )

    @api.depends("line_ids.cost_amount", "line_ids.revenue_amount")
    def _compute_amounts(self):
        for record in self:
            record.cost_amount = sum(record.line_ids.mapped("cost_amount"))
            record.revenue_amount = sum(record.line_ids.mapped("revenue_amount"))
            record.margin_amount = record.revenue_amount - record.cost_amount

    @api.model_create_multi
    def create(self, vals_list):
        records = super().create(vals_list)
        for record in records.filtered(lambda item: item.name == "New"):
            record.name = self.env["ir.sequence"].with_company(record.company_id).next_by_code(
                "construction.variation.order"
            ) or "VO/%06d" % record.id
        return records

    def write(self, vals):
        protected = {"state", "submitted_by_id", "submitted_at", "approved_by_id", "approved_at", "customer_approved_at", "revised_boq_id"}
        if protected.intersection(vals) and self.env.context.get("_construction_workflow_token") is not WORKFLOW_TOKEN:
            raise AccessError(_("Variation approvals and audit evidence are controlled by workflow actions."))
        if any(record.state in ("approved", "implemented") for record in self) and self.env.context.get("_construction_workflow_token") is not WORKFLOW_TOKEN:
            immutable = set(vals) - {"message_follower_ids", "message_partner_ids"}
            if immutable:
                raise UserError(_("An approved variation is immutable."))
        result = super().write(vals)
        self.mapped("chantier_id")._refresh_chantier_health()
        return result

    def action_submit(self):
        if any(record.state != "draft" or not record.line_ids or not record.attachment_ids for record in self):
            raise UserError(_("A variation requires priced lines and supporting evidence before submission."))
        self.with_context(_construction_workflow_token=WORKFLOW_TOKEN).write({
            "state": "submitted", "submitted_by_id": self.env.user.id, "submitted_at": fields.Datetime.now(),
        })
        return True

    def action_request_customer_approval(self):
        if any(record.state != "submitted" for record in self):
            raise UserError(_("Only internally reviewed variations can be sent to the customer."))
        self.with_context(_construction_workflow_token=WORKFLOW_TOKEN).write({"state": "customer"})
        return True

    def action_approve(self):
        if not self.env.su and not self.env.user.has_group("elmokrif_construction_control.group_construction_control_manager"):
            raise AccessError(_("Only a construction control manager can approve a variation."))
        if any(record.state != "customer" or not record.customer_approval_reference or not record.attachment_ids for record in self):
            raise UserError(_("Record the customer approval reference and signed evidence before approval."))
        self.with_context(_construction_workflow_token=WORKFLOW_TOKEN).write({
            "state": "approved", "customer_approved_at": fields.Datetime.now(),
            "approved_by_id": self.env.user.id, "approved_at": fields.Datetime.now(),
        })
        return True

    def action_prepare_boq_revision(self):
        self.ensure_one()
        if self.state != "approved":
            raise UserError(_("Approve the variation before preparing a BOQ revision."))
        if self.revised_boq_id:
            return self.revised_boq_id._form_action()
        if not self.baseline_boq_id:
            raise UserError(_("Select the current approved BOQ baseline."))
        revision = self.baseline_boq_id.with_context(
            revision_reason=_("Variation %(variation)s: %(reason)s", variation=self.name, reason=self.reason)
        ).action_create_revision()
        for variation_line in self.line_ids.filtered("boq_line_id"):
            target = revision.line_ids.filtered(lambda line: line.line_key == variation_line.boq_line_id.line_key)[:1]
            if target and variation_line.quantity_delta:
                if target.quantity_method != "manual":
                    raise UserError(_("BOQ line %s uses take-off quantities; revise its take-off evidence manually.", target.item_code))
                target.manual_quantity += variation_line.quantity_delta
        self.with_context(_construction_workflow_token=WORKFLOW_TOKEN).write({"revised_boq_id": revision.id})
        return revision._form_action()

    def action_implement(self):
        if any(record.state != "approved" for record in self):
            raise UserError(_("Only approved variations can be implemented."))
        self.with_context(_construction_workflow_token=WORKFLOW_TOKEN).write({"state": "implemented"})
        return True

    def _form_action(self):
        self.ensure_one()
        return {"type": "ir.actions.act_window", "res_model": self._name, "res_id": self.id,
                "view_mode": "form", "target": "current"}


class ConstructionVariationOrderLine(models.Model):
    _name = "construction.variation.order.line"
    _description = "Construction Variation Order Line"
    _order = "sequence, id"
    _check_company_auto = True

    sequence = fields.Integer(default=10)
    variation_id = fields.Many2one("construction.variation.order", required=True, ondelete="cascade")
    company_id = fields.Many2one(related="variation_id.company_id", store=True, readonly=True)
    currency_id = fields.Many2one(related="variation_id.currency_id", readonly=True)
    boq_line_id = fields.Many2one(
        "construction.boq.line", check_company=True, ondelete="restrict",
        domain="[('boq_id.chantier_id', '=', parent.chantier_id)]",
    )
    description = fields.Char(required=True)
    quantity_delta = fields.Float()
    cost_amount = fields.Monetary(required=True)
    revenue_amount = fields.Monetary(required=True)

    @api.constrains("quantity_delta", "cost_amount", "revenue_amount", "boq_line_id")
    def _check_values(self):
        for record in self:
            if not _finite(record.quantity_delta, record.cost_amount, record.revenue_amount):
                raise ValidationError(_("Variation quantities and amounts must be finite."))
            if record.cost_amount < 0 or record.revenue_amount < 0:
                raise ValidationError(_("Variation cost and revenue amounts cannot be negative."))
            if record.boq_line_id and record.boq_line_id.boq_id.chantier_id != record.variation_id.chantier_id:
                raise ValidationError(_("The BOQ line must belong to the variation chantier."))

    def _ensure_editable(self):
        if any(record.variation_id.state != "draft" for record in self):
            raise UserError(_("Variation lines can only be edited in Draft."))

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


class ConstructionProgressCertificate(models.Model):
    _name = "construction.progress.certificate"
    _description = "Construction Progress Certificate"
    _inherit = ["mail.thread", "mail.activity.mixin"]
    _order = "period_end desc, id desc"
    _check_company_auto = True

    name = fields.Char(default="New", readonly=True, copy=False, tracking=True)
    chantier_id = fields.Many2one(
        "project.project", required=True, check_company=True, ondelete="restrict",
        domain="[('is_chantier', '=', True), ('company_id', '=', company_id)]", tracking=True,
    )
    company_id = fields.Many2one("res.company", required=True, default=lambda self: self.env.company, readonly=True)
    currency_id = fields.Many2one(related="company_id.currency_id", readonly=True)
    customer_id = fields.Many2one(related="chantier_id.partner_id", store=True, readonly=True)
    boq_id = fields.Many2one(
        "construction.boq", required=True, check_company=True, ondelete="restrict",
        domain="[('chantier_id', '=', chantier_id), ('purpose', '=', 'client_contract'), ('is_current_revision', '=', True)]",
    )
    sale_order_id = fields.Many2one(
        "sale.order", check_company=True, ondelete="restrict",
        domain="[('chantier_id', '=', chantier_id), ('state', 'in', ['sale', 'done'])]",
    )
    billing_product_id = fields.Many2one(
        "product.product", required=True, check_company=True,
        domain="[('detailed_type', '=', 'service')]",
    )
    period_start = fields.Date(required=True, tracking=True)
    period_end = fields.Date(required=True, tracking=True)
    line_ids = fields.One2many("construction.progress.certificate.line", "certificate_id", copy=True)
    gross_current = fields.Monetary(compute="_compute_amounts", store=True)
    retention_percent = fields.Float(default=5.0, tracking=True)
    retention_amount = fields.Monetary(compute="_compute_amounts", store=True)
    advance_recovery_percent = fields.Float(default=0.0, tracking=True)
    advance_recovery_amount = fields.Monetary(compute="_compute_amounts", store=True)
    net_current = fields.Monetary(compute="_compute_amounts", store=True)
    tax_ids = fields.Many2many("account.tax", check_company=True)
    submitted_by_id = fields.Many2one("res.users", readonly=True, copy=False)
    verified_by_id = fields.Many2one("res.users", readonly=True, copy=False)
    approved_by_id = fields.Many2one("res.users", readonly=True, copy=False)
    approved_at = fields.Datetime(readonly=True, copy=False)
    customer_certificate_reference = fields.Char(copy=False, tracking=True)
    invoice_id = fields.Many2one("account.move", readonly=True, copy=False, ondelete="restrict")
    state = fields.Selection([
        ("draft", "Draft"), ("submitted", "Submitted"), ("verified", "Verified"),
        ("approved", "Approved"), ("invoiced", "Invoiced"), ("rejected", "Rejected"),
        ("cancelled", "Cancelled"),
    ], default="draft", required=True, readonly=True, tracking=True, index=True)
    attachment_ids = fields.Many2many(
        "ir.attachment", "construction_certificate_attachment_rel", "certificate_id", "attachment_id",
        string="Measurement and Approval Evidence",
    )

    @api.depends("line_ids.current_amount", "retention_percent", "advance_recovery_percent")
    def _compute_amounts(self):
        for record in self:
            record.gross_current = sum(record.line_ids.mapped("current_amount"))
            record.retention_amount = record.gross_current * record.retention_percent / 100.0
            record.advance_recovery_amount = record.gross_current * record.advance_recovery_percent / 100.0
            record.net_current = record.gross_current - record.retention_amount - record.advance_recovery_amount

    @api.model_create_multi
    def create(self, vals_list):
        records = super().create(vals_list)
        for record in records.filtered(lambda item: item.name == "New"):
            record.name = self.env["ir.sequence"].with_company(record.company_id).next_by_code(
                "construction.progress.certificate"
            ) or "PC/%06d" % record.id
        return records

    def write(self, vals):
        protected = {"state", "submitted_by_id", "verified_by_id", "approved_by_id", "approved_at", "invoice_id"}
        if protected.intersection(vals) and self.env.context.get("_construction_workflow_token") is not WORKFLOW_TOKEN:
            raise AccessError(_("Certificate status and approval evidence are controlled by workflow actions."))
        if any(record.state in ("approved", "invoiced") for record in self) and self.env.context.get("_construction_workflow_token") is not WORKFLOW_TOKEN:
            immutable = set(vals) - {"message_follower_ids", "message_partner_ids"}
            if immutable:
                raise UserError(_("An approved progress certificate is immutable."))
        return super().write(vals)

    @api.constrains("period_start", "period_end", "retention_percent", "advance_recovery_percent")
    def _check_values(self):
        for record in self:
            if record.period_end < record.period_start:
                raise ValidationError(_("The certificate period end cannot precede its start."))
            if not _finite(record.retention_percent, record.advance_recovery_percent) or not 0 <= record.retention_percent <= 100 or not 0 <= record.advance_recovery_percent <= 100:
                raise ValidationError(_("Retention and advance recovery must be between 0 and 100 percent."))
            if record.retention_percent + record.advance_recovery_percent > 100:
                raise ValidationError(_("Retention and advance recovery cannot exceed the current valuation."))

    def action_populate_boq(self):
        self.ensure_one()
        if self.state != "draft":
            raise UserError(_("BOQ lines can only be populated in Draft."))
        existing = self.line_ids.mapped("boq_line_id")
        missing = self.boq_id.line_ids.filtered(lambda line: not line.display_type and line not in existing)
        self.write({"line_ids": [Command.create({
            "boq_line_id": line.id, "description": line.description,
            "contract_quantity": line.quantity, "unit_rate": line.contract_unit_rate,
        }) for line in missing]})
        return True

    def action_submit(self):
        if any(record.state != "draft" or not record.line_ids or record.net_current <= 0 or not record.attachment_ids for record in self):
            raise UserError(_("A certificate requires measured lines, a positive net amount, and measurement evidence."))
        self.with_context(_construction_workflow_token=WORKFLOW_TOKEN).write({
            "state": "submitted", "submitted_by_id": self.env.user.id,
        })
        return True

    def action_verify(self):
        if any(record.state != "submitted" or record.submitted_by_id == self.env.user for record in self):
            raise UserError(_("A different user must verify a submitted certificate."))
        self.with_context(_construction_workflow_token=WORKFLOW_TOKEN).write({
            "state": "verified", "verified_by_id": self.env.user.id,
        })
        return True

    def action_approve(self):
        if not self.env.su and not self.env.user.has_group("elmokrif_construction_control.group_construction_control_manager"):
            raise AccessError(_("Only a construction control manager can approve a certificate."))
        if any(record.state != "verified" or record.verified_by_id == self.env.user or not record.customer_certificate_reference for record in self):
            raise UserError(_("A different manager must approve the verified certificate after recording the customer certificate reference."))
        for record in self:
            overlapping = self.search([
                ("id", "!=", record.id),
                ("chantier_id", "=", record.chantier_id.id),
                ("boq_id", "=", record.boq_id.id),
                ("state", "in", ("approved", "invoiced")),
                ("period_start", "<=", record.period_end),
                ("period_end", ">=", record.period_start),
            ], limit=1)
            if overlapping:
                raise UserError(_("Certificate periods cannot overlap an approved certificate for the same BOQ."))
        self.with_context(_construction_workflow_token=WORKFLOW_TOKEN).write({
            "state": "approved", "approved_by_id": self.env.user.id, "approved_at": fields.Datetime.now(),
        })
        return True

    def action_create_invoice(self):
        self.ensure_one()
        if self.invoice_id:
            return self.action_open_invoice()
        if self.state != "approved":
            raise UserError(_("Approve the progress certificate before invoicing."))
        if not self.customer_id:
            raise UserError(_("Set a customer on the chantier before invoicing."))
        analytic_distribution = {}
        if self.chantier_id.analytic_account_id:
            analytic_distribution = {str(self.chantier_id.analytic_account_id.id): 100.0}
        invoice = self.env["account.move"].create({
            "move_type": "out_invoice", "partner_id": self.customer_id.id,
            "company_id": self.company_id.id, "invoice_origin": self.name,
            "progress_certificate_id": self.id,
            "invoice_line_ids": [Command.create({
                "product_id": self.billing_product_id.id,
                "name": _("Progress Certificate %s (%s to %s)", self.name, self.period_start, self.period_end),
                "quantity": 1.0, "price_unit": self.net_current,
                "tax_ids": [Command.set(self.tax_ids.ids)],
                "analytic_distribution": analytic_distribution,
                "chantier_id": self.chantier_id.id,
            })],
        })
        self.with_context(_construction_workflow_token=WORKFLOW_TOKEN).write({
            "state": "invoiced", "invoice_id": invoice.id,
        })
        return self.action_open_invoice()

    def action_open_invoice(self):
        self.ensure_one()
        return {"type": "ir.actions.act_window", "name": _("Customer Invoice"),
                "res_model": "account.move", "res_id": self.invoice_id.id,
                "view_mode": "form", "target": "current"}


class ConstructionProgressCertificateLine(models.Model):
    _name = "construction.progress.certificate.line"
    _description = "Construction Progress Certificate Line"
    _order = "boq_line_id, id"
    _check_company_auto = True

    certificate_id = fields.Many2one("construction.progress.certificate", required=True, ondelete="cascade")
    company_id = fields.Many2one(related="certificate_id.company_id", store=True, readonly=True)
    currency_id = fields.Many2one(related="certificate_id.currency_id", readonly=True)
    boq_line_id = fields.Many2one(
        "construction.boq.line", required=True, check_company=True, ondelete="restrict",
        domain="[('boq_id', '=', parent.boq_id)]",
    )
    description = fields.Char(required=True)
    contract_quantity = fields.Float(required=True)
    previous_quantity = fields.Float(
        compute="_compute_previous_quantity",
        string="Previously Certified",
        readonly=True,
    )
    current_quantity = fields.Float(default=0.0)
    cumulative_quantity = fields.Float(compute="_compute_amount")
    unit_rate = fields.Monetary(required=True)
    current_amount = fields.Monetary(compute="_compute_amount")
    cumulative_amount = fields.Monetary(compute="_compute_amount")

    _sql_constraints = [
        (
            "certificate_boq_line_unique",
            "unique(certificate_id, boq_line_id)",
            "A progress certificate can contain a BOQ line only once.",
        ),
    ]

    def _compute_previous_quantity(self):
        for record in self:
            if not record.certificate_id or not record.boq_line_id:
                record.previous_quantity = 0.0
                continue
            prior_lines = self.search([
                ("certificate_id.chantier_id", "=", record.certificate_id.chantier_id.id),
                ("certificate_id.boq_id", "=", record.certificate_id.boq_id.id),
                ("certificate_id.state", "in", ("approved", "invoiced")),
                ("certificate_id.period_end", "<", record.certificate_id.period_end),
                ("boq_line_id", "=", record.boq_line_id.id),
            ])
            record.previous_quantity = sum(prior_lines.mapped("current_quantity"))

    @api.depends("current_quantity", "unit_rate", "previous_quantity")
    def _compute_amount(self):
        for record in self:
            record.cumulative_quantity = record.previous_quantity + record.current_quantity
            record.current_amount = record.current_quantity * record.unit_rate
            record.cumulative_amount = record.cumulative_quantity * record.unit_rate

    @api.constrains("contract_quantity", "previous_quantity", "current_quantity", "unit_rate", "boq_line_id")
    def _check_values(self):
        for record in self:
            values = (record.contract_quantity, record.previous_quantity, record.current_quantity, record.unit_rate)
            if not _finite(*values) or min(values) < 0:
                raise ValidationError(_("Certificate quantities and rates must be finite and non-negative."))
            if float_compare(record.cumulative_quantity, record.contract_quantity, precision_digits=3) > 0:
                raise ValidationError(_("Cumulative certified quantity cannot exceed the contract quantity."))
            if record.boq_line_id.boq_id != record.certificate_id.boq_id:
                raise ValidationError(_("Certificate lines must use the selected contract BOQ."))

    def _ensure_editable(self):
        if any(record.certificate_id.state != "draft" for record in self):
            raise UserError(_("Certificate lines can only be edited in Draft."))

    @api.model_create_multi
    def create(self, vals_list):
        if any("previous_quantity" in values for values in vals_list):
            raise AccessError(_("Previously certified quantities are derived from approved certificates."))
        records = super().create(vals_list)
        records._ensure_editable()
        return records

    def write(self, vals):
        self._ensure_editable()
        if "previous_quantity" in vals:
            raise AccessError(_("Previously certified quantities are derived from approved certificates."))
        return super().write(vals)

    def unlink(self):
        self._ensure_editable()
        return super().unlink()


class ProjectTask(models.Model):
    _inherit = "project.task"

    work_package_id = fields.Many2one(
        "construction.work.package", check_company=True, ondelete="restrict",
        domain="[('chantier_id', '=', project_id), ('state', 'not in', ['closed', 'cancelled'])]",
        tracking=True,
    )

    @api.constrains("project_id", "work_package_id")
    def _check_work_package(self):
        for task in self.filtered("work_package_id"):
            if task.work_package_id.chantier_id != task.project_id:
                raise ValidationError(_("The work package must belong to the task chantier."))


class ConstructionBOQ(models.Model):
    _inherit = "construction.boq"

    def _form_action(self):
        self.ensure_one()
        return {"type": "ir.actions.act_window", "res_model": self._name, "res_id": self.id,
                "view_mode": "form", "target": "current"}


class ProjectProject(models.Model):
    _inherit = "project.project"

    work_package_ids = fields.One2many("construction.work.package", "chantier_id")
    site_issue_ids = fields.One2many("construction.site.issue", "chantier_id")
    rfi_ids = fields.One2many("construction.rfi", "chantier_id")
    submittal_ids = fields.One2many("construction.submittal", "chantier_id")
    change_event_ids = fields.One2many("construction.change.event", "chantier_id")
    variation_order_ids = fields.One2many("construction.variation.order", "chantier_id")
    progress_certificate_ids = fields.One2many("construction.progress.certificate", "chantier_id")
    work_package_count = fields.Integer(compute="_compute_construction_control")
    open_issue_count = fields.Integer(compute="_compute_construction_control")
    overdue_rfi_count = fields.Integer(compute="_compute_construction_control")
    pending_submittal_count = fields.Integer(compute="_compute_construction_control")
    pending_change_count = fields.Integer(compute="_compute_construction_control")
    variation_order_count = fields.Integer(compute="_compute_construction_control")
    progress_certificate_count = fields.Integer(compute="_compute_construction_control")
    approved_variation_cost = fields.Monetary(compute="_compute_construction_control", currency_field="currency_id")
    approved_variation_revenue = fields.Monetary(compute="_compute_construction_control", currency_field="currency_id")
    current_budget_control = fields.Monetary(compute="_compute_construction_control", currency_field="currency_id")
    current_contract_control = fields.Monetary(compute="_compute_construction_control", currency_field="currency_id")
    forecast_cost_control = fields.Monetary(compute="_compute_construction_control", currency_field="currency_id")
    forecast_margin_control = fields.Monetary(compute="_compute_construction_control", currency_field="currency_id")
    certified_revenue_control = fields.Monetary(compute="_compute_construction_control", currency_field="currency_id")

    def _compute_construction_control(self):
        today = fields.Date.context_today(self)
        for record in self:
            record.work_package_count = len(record.work_package_ids)
            record.open_issue_count = len(record.site_issue_ids.filtered(lambda item: item.state not in ("closed", "cancelled")))
            record.overdue_rfi_count = len(record.rfi_ids.filtered(lambda item: item.response_due and item.response_due < today and item.state in ("submitted", "under_review")))
            record.pending_submittal_count = len(record.submittal_ids.filtered(lambda item: item.state in ("submitted", "under_review")))
            record.pending_change_count = len(record.change_event_ids.filtered(lambda item: item.state in ("submitted", "estimating", "review", "accepted")))
            record.variation_order_count = len(record.variation_order_ids)
            record.progress_certificate_count = len(record.progress_certificate_ids)
            approved = record.variation_order_ids.filtered(lambda item: item.state in ("approved", "implemented"))
            record.approved_variation_cost = sum(approved.mapped("cost_amount"))
            record.approved_variation_revenue = sum(approved.mapped("revenue_amount"))
            record.current_budget_control = record.approved_budget_live + record.approved_variation_cost
            client_boqs = record.boq_ids.filtered(lambda item: item.purpose == "client_contract" and item.is_current_revision and item.state in ("approved", "issued"))
            original_contract = sum(client_boqs.mapped("amount_contract"))
            record.current_contract_control = original_contract + record.approved_variation_revenue
            approved_estimates = record.estimation_ids.filtered(lambda item: item.state == "approved")
            operational_forecast = max(approved_estimates.mapped("forecast_final_cost") or [0.0])
            record.forecast_cost_control = max(
                record.actual_cost_live,
                operational_forecast + record.approved_variation_cost,
                record.current_budget_control,
            )
            record.forecast_margin_control = record.current_contract_control - record.forecast_cost_control
            approved_certificates = record.progress_certificate_ids.filtered(lambda item: item.state in ("approved", "invoiced"))
            record.certified_revenue_control = sum(approved_certificates.mapped("gross_current"))

    def _get_chantier_health(self):
        status, reason = super()._get_chantier_health()
        self.ensure_one()
        today = fields.Date.context_today(self)
        critical_issues = self.site_issue_ids.filtered(lambda item: item.state not in ("closed", "cancelled") and item.severity == "critical")
        if critical_issues:
            return "off_track", _("%(count)s critical site issue(s) require action.", count=len(critical_issues))
        overdue_rfis = self.rfi_ids.filtered(lambda item: item.response_due and item.response_due < today and item.state in ("submitted", "under_review"))
        if overdue_rfis:
            return "off_track", _("%(count)s RFI response(s) are overdue.", count=len(overdue_rfis))
        overdue_submittals = self.submittal_ids.filtered(lambda item: item.review_due and item.review_due < today and item.state in ("submitted", "under_review"))
        if overdue_submittals:
            return "at_risk", _("%(count)s submittal review(s) are overdue.", count=len(overdue_submittals))
        open_changes = self.change_event_ids.filtered(lambda item: item.state in ("submitted", "estimating", "review") and item.estimated_cost_impact > 0)
        if open_changes:
            return "at_risk", _("%(count)s unresolved priced change event(s) affect the forecast.", count=len(open_changes))
        overdue_packages = self.work_package_ids.filtered(lambda item: item.planned_finish and item.planned_finish < today and item.state not in ("accepted", "closed", "cancelled"))
        if overdue_packages:
            return "at_risk", _("%(count)s work package(s) are past their planned finish.", count=len(overdue_packages))
        return status, reason

    def _get_chantier_closure_blockers(self):
        blockers = super()._get_chantier_closure_blockers()
        self.ensure_one()
        open_packages = self.work_package_ids.filtered(lambda item: item.state not in ("accepted", "closed", "cancelled"))
        if open_packages:
            blockers.append(_("%(count)s open work package(s)", count=len(open_packages)))
        open_rfis = self.rfi_ids.filtered(lambda item: item.state not in ("closed", "cancelled"))
        if open_rfis:
            blockers.append(_("%(count)s open RFI(s)", count=len(open_rfis)))
        pending_submittals = self.submittal_ids.filtered(lambda item: item.state in ("submitted", "under_review"))
        if pending_submittals:
            blockers.append(_("%(count)s pending submittal(s)", count=len(pending_submittals)))
        pending_changes = self.change_event_ids.filtered(lambda item: item.state in ("submitted", "estimating", "review", "accepted"))
        if pending_changes:
            blockers.append(_("%(count)s unresolved change event(s)", count=len(pending_changes)))
        pending_variations = self.variation_order_ids.filtered(lambda item: item.state in ("draft", "submitted", "customer", "approved"))
        if pending_variations:
            blockers.append(_("%(count)s variation order(s) not implemented", count=len(pending_variations)))
        pending_certificates = self.progress_certificate_ids.filtered(lambda item: item.state in ("draft", "submitted", "verified", "approved"))
        if pending_certificates:
            blockers.append(_("%(count)s progress certificate(s) not invoiced", count=len(pending_certificates)))
        return blockers

    def _control_action(self, model, domain, context=None):
        self.ensure_one()
        return {"type": "ir.actions.act_window", "res_model": model, "view_mode": "tree,form",
                "domain": domain, "context": context or {}}

    def action_view_work_packages(self):
        return self._control_action("construction.work.package", [("chantier_id", "=", self.id)], {"default_chantier_id": self.id, "default_company_id": self.company_id.id})

    def action_view_site_issues(self):
        return self._control_action("construction.site.issue", [("chantier_id", "=", self.id)], {"default_chantier_id": self.id, "default_company_id": self.company_id.id})

    def action_view_rfis(self):
        return self._control_action("construction.rfi", [("chantier_id", "=", self.id)], {"default_chantier_id": self.id, "default_company_id": self.company_id.id})

    def action_view_submittals(self):
        return self._control_action("construction.submittal", [("chantier_id", "=", self.id)], {"default_chantier_id": self.id, "default_company_id": self.company_id.id})

    def action_view_variations(self):
        return self._control_action("construction.variation.order", [("chantier_id", "=", self.id)], {"default_chantier_id": self.id, "default_company_id": self.company_id.id})

    def action_view_change_events(self):
        return self._control_action("construction.change.event", [("chantier_id", "=", self.id)], {"default_chantier_id": self.id, "default_company_id": self.company_id.id})

    def action_view_progress_certificates(self):
        return self._control_action("construction.progress.certificate", [("chantier_id", "=", self.id)], {"default_chantier_id": self.id, "default_company_id": self.company_id.id})


class AccountMove(models.Model):
    _inherit = "account.move"

    progress_certificate_id = fields.Many2one(
        "construction.progress.certificate", copy=False, readonly=True, ondelete="restrict",
    )


class ElMokrifDashboard(models.Model):
    _inherit = "elmokrif.dashboard"

    active_chantier_count = fields.Integer(compute="_compute_construction_kpis")
    at_risk_chantier_count = fields.Integer(compute="_compute_construction_kpis")
    off_track_chantier_count = fields.Integer(compute="_compute_construction_kpis")
    critical_issue_count = fields.Integer(compute="_compute_construction_kpis")
    overdue_rfi_count = fields.Integer(compute="_compute_construction_kpis")
    pending_change_exposure = fields.Monetary(compute="_compute_construction_kpis", currency_field="currency_id")
    approved_variation_cost = fields.Monetary(compute="_compute_construction_kpis", currency_field="currency_id")
    certified_revenue = fields.Monetary(compute="_compute_construction_kpis", currency_field="currency_id")

    @api.depends("company_id", "as_of_date")
    def _compute_construction_kpis(self):
        for dashboard in self:
            values = {name: 0 for name in (
                "active_chantier_count", "at_risk_chantier_count", "off_track_chantier_count",
                "critical_issue_count", "overdue_rfi_count", "pending_change_exposure",
                "approved_variation_cost", "certified_revenue",
            )}
            if not dashboard.company_id:
                dashboard.update(values)
                continue
            projects = self.env["project.project"].sudo().search([
                ("company_id", "=", dashboard.company_id.id), ("is_chantier", "=", True),
                ("active", "=", True), ("chantier_state", "not in", ("closed", "completed")),
            ])
            values["active_chantier_count"] = len(projects)
            values["at_risk_chantier_count"] = len(projects.filtered(lambda item: item.last_update_status == "at_risk"))
            values["off_track_chantier_count"] = len(projects.filtered(lambda item: item.last_update_status == "off_track"))
            values["critical_issue_count"] = self.env["construction.site.issue"].sudo().search_count([
                ("company_id", "=", dashboard.company_id.id), ("severity", "=", "critical"),
                ("state", "not in", ("closed", "cancelled")),
            ])
            values["overdue_rfi_count"] = self.env["construction.rfi"].sudo().search_count([
                ("company_id", "=", dashboard.company_id.id),
                ("response_due", "<", dashboard.as_of_date),
                ("state", "in", ("submitted", "under_review")),
            ])
            changes = self.env["construction.change.event"].sudo().search([
                ("company_id", "=", dashboard.company_id.id),
                ("state", "in", ("submitted", "estimating", "review", "accepted")),
            ])
            values["pending_change_exposure"] = sum(changes.mapped("estimated_cost_impact"))
            variations = self.env["construction.variation.order"].sudo().search([
                ("company_id", "=", dashboard.company_id.id),
                ("state", "in", ("approved", "implemented")),
            ])
            values["approved_variation_cost"] = sum(variations.mapped("cost_amount"))
            certificates = self.env["construction.progress.certificate"].sudo().search([
                ("company_id", "=", dashboard.company_id.id),
                ("state", "in", ("approved", "invoiced")),
                ("period_end", "<=", dashboard.as_of_date),
            ])
            values["certified_revenue"] = sum(certificates.mapped("gross_current"))
            dashboard.update(values)
