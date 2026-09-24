from odoo import _, fields, models
from odoo.exceptions import ValidationError


class ConstructionBOQReturnWizard(models.TransientModel):
    _name = "construction.boq.return.wizard"
    _description = "Request BOQ Changes"

    boq_id = fields.Many2one("construction.boq", required=True, readonly=True)
    reason = fields.Text(required=True)

    def action_confirm(self):
        self.ensure_one()
        if not (self.reason or "").strip():
            raise ValidationError(_("Enter a clear reason for the requested changes."))
        self.boq_id.with_context(review_comment=self.reason.strip()).action_request_changes()
        return {"type": "ir.actions.act_window_close"}


class ConstructionBOQRevisionWizard(models.TransientModel):
    _name = "construction.boq.revision.wizard"
    _description = "Create BOQ Revision"

    boq_id = fields.Many2one("construction.boq", required=True, readonly=True)
    reason = fields.Text(required=True)

    def action_confirm(self):
        self.ensure_one()
        if not (self.reason or "").strip():
            raise ValidationError(_("Enter the contractual or technical reason for this revision."))
        revision = self.boq_id.with_context(revision_reason=self.reason.strip()).action_create_revision()
        return {
            "type": "ir.actions.act_window",
            "name": _("BOQ Revision"),
            "res_model": "construction.boq",
            "view_mode": "form",
            "res_id": revision.id,
            "target": "current",
        }
