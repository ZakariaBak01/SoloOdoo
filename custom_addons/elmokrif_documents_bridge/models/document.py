from datetime import timedelta

from odoo import _, api, fields, models
from odoo.exceptions import AccessError, UserError, ValidationError

_DOCUMENT_WORKFLOW_TOKEN = object()

class ElMokrifDocument(models.Model):
    _name = "elmokrif.document"
    _description = "EL MOKRIF Controlled Document"
    _inherit = ["mail.thread", "mail.activity.mixin"]
    _order = "chantier_id, category, name, revision desc"
    _check_company_auto = True

    name = fields.Char(required=True, tracking=True)
    company_id = fields.Many2one(
        "res.company", required=True, default=lambda self: self.env.company,
        tracking=True,
    )
    chantier_id = fields.Many2one(
        "project.project", string="Chantier", tracking=True, check_company=True,
        domain="[('is_chantier', '=', True), ('company_id', '=', company_id)]",
    )
    category = fields.Selection([
        ("contract", "Contract"), ("quotation", "Quotation"),
        ("invoice", "Invoice"), ("delivery_note", "Delivery Note"),
        ("drawing", "Drawing"), ("inspection", "Inspection"),
        ("certificate", "Certificate"), ("other", "Other"),
    ], required=True, default="other", tracking=True)
    owner_id = fields.Many2one(
        "res.users", required=True, default=lambda self: self.env.user, tracking=True,
    )
    issue_date = fields.Date(default=fields.Date.context_today, required=True, tracking=True)
    expiry_date = fields.Date(tracking=True)
    revision = fields.Integer(default=1, required=True, readonly=True, tracking=True)
    state = fields.Selection([
        ("draft", "Draft"), ("in_review", "In Review"),
        ("approved", "Approved"), ("rejected", "Rejected"),
        ("superseded", "Superseded"), ("archived", "Archived"),
    ], default="draft", required=True, readonly=True, copy=False, tracking=True)
    attachment_id = fields.Many2one(
        "ir.attachment", required=True, ondelete="restrict",
    )
    previous_revision_id = fields.Many2one(
        "elmokrif.document", ondelete="restrict", copy=False, readonly=True,
        check_company=True,
    )
    successor_revision_id = fields.Many2one(
        "elmokrif.document", ondelete="restrict", copy=False, readonly=True,
        check_company=True,
    )
    expiry_activity_id = fields.Many2one(
        "mail.activity", copy=False, readonly=True, ondelete="set null",
    )
    reviewed_by_id = fields.Many2one(
        "res.users", string="Last Reviewed By", copy=False, readonly=True,
        tracking=True,
    )
    reviewed_at = fields.Datetime(
        string="Last Reviewed On", copy=False, readonly=True, tracking=True,
    )
    decision_reason = fields.Text(
        string="Last Decision Reason", copy=False, readonly=True, tracking=True,
    )

    _sql_constraints = [
        ("previous_revision_unique", "unique(previous_revision_id)",
         "A document revision can have only one successor."),
    ]

    @api.constrains("expiry_date", "issue_date")
    def _check_dates(self):
        for document in self:
            if document.expiry_date and document.expiry_date < document.issue_date:
                raise ValidationError(_("The expiry date cannot precede the issue date."))

    @api.model_create_multi
    def create(self, values_list):
        workflow_fields = {
            "state", "revision", "previous_revision_id", "successor_revision_id",
            "expiry_activity_id", "reviewed_by_id", "reviewed_at",
            "decision_reason",
        }
        in_workflow = self.env.context.get("_elmokrif_document_workflow_token") is _DOCUMENT_WORKFLOW_TOKEN
        if not in_workflow and (
            any(workflow_fields.intersection(values) for values in values_list)
            or any("default_%s" % field in self.env.context for field in workflow_fields)
        ):
            raise UserError(_("Document workflow evidence is managed by the document actions."))
        documents = super().create(values_list)
        for document in documents:
            document._bind_attachment()
        return documents

    def _bind_attachment(self):
        """Link an attachment only after checking that the user may read it."""
        for document in self:
            attachment = document.attachment_id
            attachment.check_access_rights("read")
            attachment.check("read")
            attachment_values = {
                "company_id": document.company_id.id,
                "res_model": self._name,
                "res_id": document.id,
                "public": False,
                "access_token": False,
            }
            # A revision must own its file. Reusing the same ir.attachment would
            # relink and silently remove the previous revision's evidence.
            if attachment.res_model and attachment.res_id:
                attachment = attachment.sudo().copy(attachment_values)
                super(ElMokrifDocument, document).write({"attachment_id": attachment.id})
            else:
                attachment.sudo().with_context(
                    _elmokrif_document_workflow_token=_DOCUMENT_WORKFLOW_TOKEN,
                ).write(attachment_values)

    def _lock_for_workflow(self):
        self.check_access_rights("write")
        self.check_access_rule("write")
        self.flush_recordset(["state", "successor_revision_id"])
        if self.ids:
            self.env.cr.execute(
                "SELECT id FROM elmokrif_document WHERE id IN %s ORDER BY id FOR UPDATE",
                [tuple(self.ids)],
            )
            self.invalidate_recordset(["state", "successor_revision_id"])

    def _workflow_write(self, values):
        return self.with_context(_elmokrif_document_workflow_token=_DOCUMENT_WORKFLOW_TOKEN).write(values)

    @api.constrains("chantier_id", "company_id", "attachment_id")
    def _check_chantier_company(self):
        for document in self:
            if document.chantier_id and document.chantier_id.company_id != document.company_id:
                raise ValidationError(_("The document and chantier must use the same company."))
            if document.attachment_id.company_id and document.attachment_id.company_id != document.company_id:
                raise ValidationError(_("The attachment must be shared or belong to the document company."))

    def write(self, values):
        protected = {
            "name", "company_id", "chantier_id", "category", "owner_id", "issue_date",
            "expiry_date", "attachment_id", "revision", "previous_revision_id",
            "successor_revision_id",
        }
        in_workflow = self.env.context.get("_elmokrif_document_workflow_token") is _DOCUMENT_WORKFLOW_TOKEN
        workflow_fields = {
            "state", "revision", "previous_revision_id", "successor_revision_id",
            "expiry_activity_id", "reviewed_by_id", "reviewed_at",
            "decision_reason",
        }
        if workflow_fields.intersection(values) and not in_workflow:
            raise UserError(_("Document workflow evidence is managed by the document actions."))
        if protected.intersection(values) or "state" in values:
            self._lock_for_workflow()
        if protected.intersection(values) and any(document.state not in ("draft", "rejected") for document in self) and not in_workflow:
            raise UserError(_("Only draft or rejected documents can be changed."))
        if "state" in values and not in_workflow:
            raise UserError(_("Use the document workflow actions to change its state."))
        result = super().write(values)
        if "attachment_id" in values:
            self._bind_attachment()
        return result

    def unlink(self):
        if any(document.state not in ("draft", "rejected") for document in self):
            raise UserError(_("Only draft or rejected documents can be deleted."))
        return super().unlink()

    def _ensure_manager(self):
        if not (
            self.env.su
            or self.env.user.has_group("elmokrif_documents_bridge.group_elmokrif_document_manager")
        ):
            raise AccessError(_("Only a document manager can perform this action."))

    def action_submit_for_review(self):
        self._lock_for_workflow()
        if any(document.state not in ("draft", "rejected") for document in self):
            raise UserError(_("Only a draft or rejected document can be submitted for review."))
        self._workflow_write({"state": "in_review"})
        for document in self:
            document._message_log(body=_("Revision %s was submitted for review.") % document.revision)
        return True

    def action_approve(self):
        self._ensure_manager()
        documents_to_lock = self | self.mapped("previous_revision_id")
        documents_to_lock._lock_for_workflow()
        for document in self:
            if document.state != "in_review":
                raise UserError(_("Only a document in review can be approved."))
            predecessor = document.previous_revision_id
            if predecessor and predecessor.state != "approved":
                raise UserError(
                    _("The preceding revision must still be approved before this revision can replace it.")
                )
        decision_time = fields.Datetime.now()
        for document in self:
            predecessor = document.previous_revision_id
            if predecessor:
                predecessor._workflow_write({"state": "superseded"})
                predecessor._message_log(
                    body=_("Superseded by approved revision %s.") % document.revision
                )
            document._workflow_write({
                "state": "approved",
                "reviewed_by_id": self.env.user.id,
                "reviewed_at": decision_time,
                "decision_reason": False,
            })
            document._message_log(
                body=_("Revision %(revision)s approved by %(reviewer)s on %(date)s.") % {
                    "revision": document.revision,
                    "reviewer": self.env.user.display_name,
                    "date": fields.Datetime.to_string(decision_time),
                }
            )
        return True

    def action_open_reject_wizard(self):
        self._ensure_manager()
        self._lock_for_workflow()
        if any(document.state != "in_review" for document in self):
            raise UserError(_("Only a document in review can be rejected."))
        self.ensure_one()
        return {
            "type": "ir.actions.act_window",
            "name": _("Reject Controlled Document"),
            "res_model": "elmokrif.document.reject.wizard",
            "view_mode": "form",
            "target": "new",
            "context": {"default_document_id": self.id},
        }

    def _action_reject(self, reason):
        self._ensure_manager()
        reason = (reason or "").strip()
        if not reason:
            raise ValidationError(_("A rejection reason is required."))
        self._lock_for_workflow()
        if any(document.state != "in_review" for document in self):
            raise UserError(_("Only a document in review can be rejected."))
        decision_time = fields.Datetime.now()
        for document in self:
            document._workflow_write({
                "state": "rejected",
                "reviewed_by_id": self.env.user.id,
                "reviewed_at": decision_time,
                "decision_reason": reason,
            })
            document._message_log(
                body=_("Revision %(revision)s rejected by %(reviewer)s on %(date)s. Reason: %(reason)s") % {
                    "revision": document.revision,
                    "reviewer": self.env.user.display_name,
                    "date": fields.Datetime.to_string(decision_time),
                    "reason": reason,
                }
            )
        return True

    def action_create_revision(self):
        self.ensure_one()
        self._ensure_manager()
        self._lock_for_workflow()
        if self.state != "approved":
            raise UserError(_("Only an approved document can be revised."))
        if self.successor_revision_id:
            return {
                "type": "ir.actions.act_window", "res_model": "elmokrif.document",
                "view_mode": "form", "res_id": self.successor_revision_id.id,
            }
        revision = self.with_context(
            _elmokrif_document_workflow_token=_DOCUMENT_WORKFLOW_TOKEN
        ).copy({
            "revision": self.revision + 1,
            "state": "draft",
            "previous_revision_id": self.id,
            "successor_revision_id": False,
            "expiry_activity_id": False,
            "reviewed_by_id": False,
            "reviewed_at": False,
            "decision_reason": False,
        })
        self._workflow_write({"successor_revision_id": revision.id})
        self._message_log(
            body=_("Draft revision %s was created; this approved revision remains current until approval.")
            % revision.revision
        )
        return {
            "type": "ir.actions.act_window", "res_model": "elmokrif.document",
            "view_mode": "form", "res_id": revision.id,
        }

    def action_archive(self):
        self._ensure_manager()
        self._lock_for_workflow()
        if any(document.state not in ("approved", "superseded") for document in self):
            raise UserError(_("Only an approved or superseded document can be archived."))
        self._workflow_write({"state": "archived"})
        return True

    @api.model
    def _cron_schedule_expiry_activities(self):
        deadline = fields.Date.today() + timedelta(days=30)
        documents = self.search([
            ("state", "=", "approved"), ("expiry_date", "!=", False),
            ("expiry_date", "<=", deadline),
            ("expiry_activity_id", "=", False),
        ])
        activity_type = self.env.ref("mail.mail_activity_data_todo")
        for document in documents:
            activity = document.activity_schedule(
                activity_type_id=activity_type.id,
                user_id=document.owner_id.id,
                date_deadline=document.expiry_date,
                summary=_("Document expiry"),
                note=_("Review the approaching expiry of %s.") % document.name,
            )
            document._workflow_write({"expiry_activity_id": activity.id})
        return True
