from odoo import _, fields, models
from odoo.exceptions import ValidationError


class ElMokrifDocumentRejectWizard(models.TransientModel):
    _name = "elmokrif.document.reject.wizard"
    _description = "Controlled Document Rejection"

    document_id = fields.Many2one(
        "elmokrif.document", required=True, readonly=True, ondelete="cascade",
    )
    reason = fields.Text(required=True)

    def action_confirm(self):
        self.ensure_one()
        if not (self.reason or "").strip():
            raise ValidationError(_("A rejection reason is required."))
        self.document_id._action_reject(self.reason)
        return {"type": "ir.actions.act_window_close"}
