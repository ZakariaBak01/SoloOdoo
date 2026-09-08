from odoo import _, models
from odoo.exceptions import UserError

from .document import _DOCUMENT_WORKFLOW_TOKEN


class IrAttachment(models.Model):
    _inherit = "ir.attachment"

    def _controlled_documents(self):
        # Search with elevated access only to enforce protection even if the
        # caller cannot see the document. The attachment operation keeps its ACL.
        return self.env["elmokrif.document"].sudo().search([
            ("attachment_id", "in", self.ids),
        ])

    def write(self, values):
        documents = self._controlled_documents()
        in_workflow = self.env.context.get("_elmokrif_document_workflow_token") is _DOCUMENT_WORKFLOW_TOKEN
        if documents and not in_workflow:
            if {"res_model", "res_id", "res_field", "company_id", "public", "access_token"}.intersection(values):
                raise UserError(_("Controlled document files cannot be relinked or shared publicly."))
            documents._lock_for_workflow()
            if any(document.state not in ("draft", "rejected") for document in documents):
                raise UserError(_("Create a document revision before changing an approved or reviewed file."))
        return super().write(values)

    def unlink(self):
        if self._controlled_documents():
            raise UserError(_("Remove or replace the file from its draft document first."))
        return super().unlink()
