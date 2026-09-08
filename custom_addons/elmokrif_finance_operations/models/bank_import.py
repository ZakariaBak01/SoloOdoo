import base64
import csv
import hashlib
import io
import math
from datetime import datetime
from decimal import Decimal, InvalidOperation

from odoo import _, api, fields, models
from odoo.exceptions import AccessError, UserError, ValidationError

_BANK_IMPORT_WORKFLOW_TOKEN = object()

class ElMokrifBankImport(models.Model):
    _name = "elmokrif.bank.import"
    _description = "EL MOKRIF Bank Statement Import"
    _inherit = ["mail.thread", "mail.activity.mixin"]
    _order = "imported_at desc, id desc"
    _check_company_auto = True

    name = fields.Char(required=True, default=lambda self: _("Bank file"))
    company_id = fields.Many2one("res.company", required=True, default=lambda self: self.env.company)
    journal_id = fields.Many2one(
        "account.journal", required=True, check_company=True,
        domain="[('company_id', '=', company_id), ('type', '=', 'bank')]",
    )
    file_name = fields.Char(required=True)
    file_content = fields.Binary(required=True, attachment=True)
    state = fields.Selection([
        ("draft", "Draft"), ("imported", "Imported for Review"), ("closed", "Closed"),
    ], default="draft", required=True, readonly=True, tracking=True)
    imported_at = fields.Datetime(readonly=True, copy=False)
    line_ids = fields.One2many("elmokrif.bank.import.line", "import_id", readonly=True)
    line_count = fields.Integer(compute="_compute_line_count")

    def _compute_line_count(self):
        for statement in self:
            statement.line_count = len(statement.line_ids)

    @api.constrains("journal_id", "company_id")
    def _check_journal_company(self):
        for statement in self:
            if statement.journal_id.company_id != statement.company_id:
                raise ValidationError(_("The bank journal must use the import company."))
            if statement.journal_id.type != "bank":
                raise ValidationError(_("Bank files require a bank journal."))

    def _ensure_accountant(self):
        if not (self.env.su or self.env.user.has_group("account.group_account_manager")):
            raise AccessError(_("Only an Accounting Administrator can import or review bank files."))

    @api.model_create_multi
    def create(self, values_list):
        workflow_fields = {"state", "imported_at", "line_ids"}
        default_fields = {key[8:] for key in self.env.context if key.startswith("default_")}
        in_workflow = self.env.context.get("_elmokrif_bank_import_workflow_token") is _BANK_IMPORT_WORKFLOW_TOKEN
        if not in_workflow and (workflow_fields.intersection(default_fields) or any(workflow_fields.intersection(values) for values in values_list)):
            raise UserError(_("Bank import workflow evidence is managed by the import actions."))
        return super().create(values_list)

    def _workflow_write(self, values):
        return self.with_context(_elmokrif_bank_import_workflow_token=_BANK_IMPORT_WORKFLOW_TOKEN).write(values)

    def write(self, values):
        protected = {"company_id", "journal_id", "file_name", "file_content", "state", "imported_at"}
        in_workflow = self.env.context.get("_elmokrif_bank_import_workflow_token") is _BANK_IMPORT_WORKFLOW_TOKEN
        if protected.intersection(values) and any(statement.state != "draft" for statement in self) and not in_workflow:
            raise UserError(_("An imported bank file is immutable."))
        if {"state", "imported_at"}.intersection(values) and not in_workflow:
            raise UserError(_("Use the bank import workflow actions to change its state."))
        return super().write(values)

    def unlink(self):
        if any(statement.state != "draft" or statement.line_ids for statement in self):
            raise AccessError(_("Imported bank files are retained as an audit trail."))
        return super().unlink()

    @api.model
    def _parse_date(self, value):
        for format_string in ("%Y-%m-%d", "%d/%m/%Y", "%d-%m-%Y"):
            try:
                return datetime.strptime((value or "").strip(), format_string).date()
            except ValueError:
                continue
        raise ValidationError(_("Invalid statement date '%s'. Use YYYY-MM-DD or DD/MM/YYYY.") % value)

    @api.model
    def _parse_amount(self, value):
        try:
            amount = Decimal((value or "").replace(" ", "").replace(",", "."))
        except (InvalidOperation, ValueError):
            raise ValidationError(_("Invalid statement amount '%s'.") % value)
        if not amount.is_finite() or not math.isfinite(float(amount)):
            raise ValidationError(_("Invalid statement amount '%s'.") % value)
        return float(amount)

    def action_import_file(self):
        self._ensure_accountant()
        for statement in self:
            if statement.state != "draft":
                raise UserError(_("A bank file can only be imported once."))
            try:
                raw = base64.b64decode(statement.file_content, validate=True).decode("utf-8-sig")
            except (ValueError, UnicodeDecodeError):
                raise ValidationError(_("Upload a UTF-8 CSV bank file."))
            reader = csv.DictReader(io.StringIO(raw))
            expected = {"date", "amount", "reference"}
            fields_found = {field.strip().lower() for field in (reader.fieldnames or [])}
            if not expected.issubset(fields_found):
                raise ValidationError(_("The CSV must contain date, amount and reference headers."))
            values = []
            seen_keys = set()
            for row_number, source in enumerate(reader, start=2):
                if None in source:
                    raise ValidationError(_("Invalid CSV column count on line %s.") % row_number)
                row = {(key or "").strip().lower(): (value or "").strip() for key, value in source.items()}
                date = self._parse_date(row.get("date"))
                amount = self._parse_amount(row.get("amount"))
                reference = row.get("reference")
                key_data = "|".join((str(date), str(amount), reference, row.get("partner", ""), row.get("account", "")))
                external_key = hashlib.sha256(key_data.encode()).hexdigest()
                if external_key in seen_keys:
                    continue
                seen_keys.add(external_key)
                duplicate = self.env["elmokrif.bank.import.line"].search_count([
                    ("company_id", "=", statement.company_id.id), ("journal_id", "=", statement.journal_id.id),
                    ("external_key", "=", external_key),
                ])
                if duplicate:
                    continue
                values.append({
                    "import_id": statement.id, "company_id": statement.company_id.id,
                    "journal_id": statement.journal_id.id, "line_number": row_number, "date": date,
                    "amount": amount, "reference": reference, "partner_name": row.get("partner"),
                    "account_number": row.get("account"), "external_key": external_key,
                })
            if values:
                self.env["elmokrif.bank.import.line"].with_context(
                    _elmokrif_bank_import_workflow_token=_BANK_IMPORT_WORKFLOW_TOKEN
                ).create(values)
            else:
                raise UserError(_("This file contains no new bank lines to review."))
            statement._workflow_write({"state": "imported", "imported_at": fields.Datetime.now()})
        return True

    def action_close(self):
        self._ensure_accountant()
        for statement in self:
            if statement.state != "imported" or any(line.state == "new" for line in statement.line_ids):
                raise UserError(_("Review or explicitly mark every imported bank line before closing the file."))
        self._workflow_write({"state": "closed"})
        return True


class ElMokrifBankImportLine(models.Model):
    _name = "elmokrif.bank.import.line"
    _description = "EL MOKRIF Imported Bank Line"
    _order = "date, id"
    _check_company_auto = True

    import_id = fields.Many2one("elmokrif.bank.import", required=True, ondelete="cascade")
    company_id = fields.Many2one("res.company", required=True, readonly=True)
    journal_id = fields.Many2one("account.journal", required=True, readonly=True, check_company=True)
    line_number = fields.Integer(required=True, readonly=True)
    date = fields.Date(required=True, readonly=True)
    amount = fields.Monetary(required=True, readonly=True, currency_field="currency_id")
    currency_id = fields.Many2one("res.currency", compute="_compute_currency_id", store=True, readonly=True)
    reference = fields.Char(readonly=True)
    partner_name = fields.Char(readonly=True)
    account_number = fields.Char(readonly=True)
    external_key = fields.Char(required=True, readonly=True, index=True)
    state = fields.Selection([
        ("new", "Needs Review"), ("matched", "Matched"), ("unmatched", "Unmatched"), ("ignored", "Ignored"),
    ], default="new", required=True, readonly=True)
    matched_payment_id = fields.Many2one("account.payment", check_company=True, ondelete="restrict")
    review_note = fields.Text()

    _sql_constraints = [
        ("external_key_journal_unique", "unique(company_id, journal_id, external_key)", "This statement line was already imported."),
    ]

    def init(self):
        self.env.cr.execute("""
            CREATE UNIQUE INDEX IF NOT EXISTS elmokrif_bank_line_confirmed_payment_unique
            ON elmokrif_bank_import_line (matched_payment_id)
            WHERE state = 'matched' AND matched_payment_id IS NOT NULL
        """)

    @api.depends("journal_id", "company_id")
    def _compute_currency_id(self):
        for line in self:
            line.currency_id = line.journal_id.currency_id or line.company_id.currency_id

    @api.model_create_multi
    def create(self, values_list):
        if self.env.context.get("_elmokrif_bank_import_workflow_token") is not _BANK_IMPORT_WORKFLOW_TOKEN:
            raise AccessError(_("Bank lines can only be created from an imported file."))
        return super().create(values_list)

    def _workflow_write(self, values):
        return self.with_context(_elmokrif_bank_import_workflow_token=_BANK_IMPORT_WORKFLOW_TOKEN).write(values)

    def _validate_payment_match(self, payment):
        self.ensure_one()
        if (
            not payment.exists()
            or not self.amount
            or payment.company_id != self.company_id
            or payment.journal_id != self.journal_id
            or payment.state != "posted"
            or payment.currency_id != self.currency_id
            or payment.payment_type != ("inbound" if self.amount > 0 else "outbound")
            or self.currency_id.compare_amounts(payment.amount, abs(self.amount)) != 0
            or payment.ref != self.reference
        ):
            raise ValidationError(_("The selected payment is not an exact match for this bank line."))
        if self.search_count([
            ("id", "!=", self.id), ("state", "=", "matched"),
            ("matched_payment_id", "=", payment.id),
        ]):
            raise ValidationError(_("This payment is already matched to another bank line."))

    def write(self, values):
        source_fields = {
            "import_id", "company_id", "journal_id", "line_number", "date", "amount", "reference",
            "partner_name", "account_number", "external_key", "currency_id",
        }
        in_workflow = self.env.context.get("_elmokrif_bank_import_workflow_token") is _BANK_IMPORT_WORKFLOW_TOKEN
        if source_fields.intersection(values):
            raise AccessError(_("Imported bank statement data is immutable."))
        if "state" in values and not in_workflow:
            raise UserError(_("Use the bank review actions to change a line state."))
        if {"matched_payment_id", "review_note"}.intersection(values) and any(line.state != "new" for line in self):
            raise UserError(_("Only a bank line awaiting review can be changed."))
        if values.get("matched_payment_id"):
            payment = self.env["account.payment"].browse(values["matched_payment_id"])
            for line in self:
                line._validate_payment_match(payment)
        return super().write(values)

    def unlink(self):
        raise AccessError(_("Imported bank lines are retained as an audit trail."))

    def _ensure_accountant(self):
        if not (self.env.su or self.env.user.has_group("account.group_account_manager")):
            raise AccessError(_("Only an Accounting Administrator can review bank lines."))

    def action_suggest_payment(self):
        self._ensure_accountant()
        for line in self:
            payments = self.env["account.payment"].search([
                ("company_id", "=", line.company_id.id), ("journal_id", "=", line.journal_id.id),
                ("state", "=", "posted"), ("amount", "=", abs(line.amount)),
                ("ref", "=", line.reference),
                ("currency_id", "=", line.currency_id.id),
                ("payment_type", "=", "inbound" if line.amount > 0 else "outbound"),
                ("id", "not in", self.search([("state", "=", "matched")]).matched_payment_id.ids),
            ], limit=2)
            if len(payments) == 1:
                line.write({"matched_payment_id": payments.id})
        return True

    def action_confirm_match(self):
        self._ensure_accountant()
        for line in self:
            if line.state != "new" or not line.matched_payment_id:
                raise UserError(_("Choose a posted payment before confirming a bank match."))
            self.env.cr.execute("SELECT id FROM account_payment WHERE id = %s FOR UPDATE", [line.matched_payment_id.id])
            line.matched_payment_id.invalidate_recordset()
            line._validate_payment_match(line.matched_payment_id)
            line._workflow_write({"state": "matched"})
        return True

    def action_mark_unmatched(self):
        self._ensure_accountant()
        if any(line.state != "new" for line in self):
            raise UserError(_("Only a bank line awaiting review can be marked unmatched."))
        self._workflow_write({"state": "unmatched", "matched_payment_id": False})
        return True

    def action_ignore(self):
        self._ensure_accountant()
        if any(not line.review_note for line in self):
            raise UserError(_("Record a review note before ignoring a bank line."))
        if any(line.state != "new" for line in self):
            raise UserError(_("Only a bank line awaiting review can be ignored."))
        self._workflow_write({"state": "ignored", "matched_payment_id": False})
        return True
