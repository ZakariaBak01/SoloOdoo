import base64
from datetime import timedelta

from odoo import Command, fields
from odoo.exceptions import AccessError, UserError
from odoo.tests import TransactionCase, tagged


@tagged("post_install", "-at_install")
class TestControlledDocument(TransactionCase):
    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.user = cls._user("Document Author", "document.author@example.test", "elmokrif_documents_bridge.group_elmokrif_document_user")
        cls.manager = cls._user("Document Manager", "document.manager@example.test", "elmokrif_documents_bridge.group_elmokrif_document_manager")

    @classmethod
    def _user(cls, name, login, group):
        return cls.env["res.users"].with_context(no_reset_password=True).create({
            "name": name, "login": login, "company_id": cls.env.company.id,
            "company_ids": [Command.set([cls.env.company.id])],
            "groups_id": [Command.set([cls.env.ref("base.group_user").id, cls.env.ref(group).id])],
        })

    def _document(self):
        attachment = self.env["ir.attachment"].with_user(self.user).create({
            "name": "contract-v1.pdf", "datas": base64.b64encode(b"revision one"),
        })
        return self.env["elmokrif.document"].with_user(self.user).create({
            "name": "Customer contract", "category": "contract",
            "attachment_id": attachment.id,
        })

    def test_review_approval_and_revision_preserve_evidence(self):
        document = self._document()
        document.with_user(self.user).action_submit_for_review()
        with self.assertRaises(UserError):
            document.with_user(self.user).write({"state": "approved"})
        document.with_user(self.manager).action_approve()
        action = document.with_user(self.manager).action_create_revision()
        revision = self.env["elmokrif.document"].browse(action["res_id"])
        self.assertEqual(document.state, "approved")
        self.assertEqual(revision.revision, 2)
        self.assertEqual(revision.previous_revision_id, document)
        self.assertNotEqual(revision.attachment_id, document.attachment_id)
        self.assertEqual(revision.attachment_id.raw, document.attachment_id.raw)
        revision.with_user(self.user).action_submit_for_review()
        revision.with_user(self.manager).action_approve()
        self.assertEqual(document.state, "superseded")
        self.assertEqual(revision.state, "approved")
        self.assertEqual(revision.reviewed_by_id, self.manager)
        self.assertTrue(revision.reviewed_at)

    def test_rejection_requires_reason_and_retains_review_evidence(self):
        document = self._document()
        document.with_user(self.user).action_submit_for_review()
        with self.assertRaises(UserError):
            document.with_user(self.manager)._action_reject("  ")
        document.with_user(self.manager)._action_reject("Missing signature")
        self.assertEqual(document.state, "rejected")
        self.assertEqual(document.reviewed_by_id, self.manager)
        self.assertTrue(document.reviewed_at)
        self.assertEqual(document.decision_reason, "Missing signature")

    def test_expiry_job_includes_past_due_and_is_idempotent(self):
        document = self._document()
        document.with_user(self.user).write({
            "issue_date": fields.Date.today() - timedelta(days=30),
            "expiry_date": fields.Date.today() - timedelta(days=1),
        })
        document.with_user(self.user).action_submit_for_review()
        document.with_user(self.manager).action_approve()

        self.env["elmokrif.document"]._cron_schedule_expiry_activities()
        first_activity = document.expiry_activity_id
        self.assertTrue(first_activity)
        self.assertEqual(first_activity.user_id, self.user)
        self.assertEqual(first_activity.date_deadline, document.expiry_date)

        self.env["elmokrif.document"]._cron_schedule_expiry_activities()
        self.assertEqual(document.expiry_activity_id, first_activity)
        self.assertEqual(self.env["mail.activity"].search_count([
            ("res_model", "=", "elmokrif.document"),
            ("res_id", "=", document.id),
            ("summary", "=", "Document expiry"),
        ]), 1)

    def test_create_cannot_forge_document_workflow(self):
        attachment = self.env["ir.attachment"].create({
            "name": "forged.pdf", "datas": base64.b64encode(b"forged"),
        })
        with self.assertRaises(UserError):
            self.env["elmokrif.document"].create({
                "name": "Forged approval", "category": "contract",
                "attachment_id": attachment.id, "state": "approved", "revision": 9,
            })

    def test_draft_cannot_forge_revision_or_expiry_evidence(self):
        document = self._document()
        for values in ({"revision": 99}, {"previous_revision_id": document.id}, {"expiry_activity_id": False}):
            with self.assertRaises(UserError):
                document.with_context(elmokrif_document_workflow=True).write(values)
        with self.assertRaises(UserError):
            self.env["elmokrif.document"].with_context(default_state="approved").create({
                "name": "Forged by default", "attachment_id": document.attachment_id.id,
            })

    def test_approved_file_cannot_be_changed_relinked_or_published(self):
        document = self._document()
        document.action_submit_for_review()
        document.with_user(self.manager).action_approve()
        for values in (
            {"datas": base64.b64encode(b"tampered evidence")},
            {"res_id": 0}, {"public": True}, {"access_token": "public-token"},
        ):
            with self.assertRaises(UserError):
                document.attachment_id.with_user(self.user).write(values)
        with self.assertRaises(UserError):
            document.attachment_id.with_user(self.manager).unlink()
        self.assertEqual(document.attachment_id.raw, b"revision one")

    def test_other_users_unattached_file_cannot_be_claimed(self):
        attachment = self.env["ir.attachment"].with_user(self.manager).create({
            "name": "private.pdf", "datas": base64.b64encode(b"private evidence"),
        })
        with self.assertRaises(AccessError), self.cr.savepoint():
            self.env["elmokrif.document"].with_user(self.user).create({
                "name": "Claimed file", "attachment_id": attachment.id,
            })
        self.assertFalse(attachment.res_id)

    def test_public_upload_is_private_after_binding_and_revision_is_independent(self):
        attachment = self.env["ir.attachment"].with_user(self.user).create({
            "name": "upload.pdf", "datas": base64.b64encode(b"original evidence"),
            "public": True, "access_token": "old-token",
        })
        document = self.env["elmokrif.document"].with_user(self.user).create({
            "name": "Controlled upload", "attachment_id": attachment.id,
        })
        self.assertFalse(document.attachment_id.public)
        self.assertFalse(document.attachment_id.access_token)
        document.action_submit_for_review()
        document.with_user(self.manager).action_approve()
        action = document.with_user(self.manager).action_create_revision()
        revision = self.env["elmokrif.document"].browse(action["res_id"])
        revision.attachment_id.with_user(self.user).write({"datas": base64.b64encode(b"new evidence")})
        self.assertEqual(document.attachment_id.raw, b"original evidence")
        self.assertEqual(revision.attachment_id.raw, b"new evidence")
        repeated_action = document.with_user(self.manager).action_create_revision()
        self.assertEqual(repeated_action["res_id"], revision.id)
