from odoo import _, api, fields, models
from odoo.exceptions import AccessError, UserError

_CHEQUE_WORKFLOW_TOKEN = object()

class AccountPayment(models.Model):
    _inherit = "account.payment"

    elmokrif_cheque_number = fields.Char(string="Cheque Number", copy=False, tracking=True)
    # account.payment delegates company_id to account.move, so that field has
    # no column on account_payment and cannot be used in a SQL constraint.
    elmokrif_cheque_company_id = fields.Many2one(
        "res.company", string="Cheque Company", related="move_id.company_id",
        store=True, readonly=True,
    )
    elmokrif_cheque_state = fields.Selection([
        ("draft", "Not Printed"), ("printed", "Printed"), ("void", "Voided"),
    ], default="draft", readonly=True, copy=False, tracking=True)
    elmokrif_cheque_void_reason = fields.Text(string="Cheque Void Reason", copy=False, tracking=True)
    elmokrif_cheque_printed_at = fields.Datetime(readonly=True, copy=False, tracking=True)
    elmokrif_cheque_printed_by_id = fields.Many2one("res.users", readonly=True, copy=False, tracking=True)

    _sql_constraints = [
        ("elmokrif_cheque_company_unique", "unique(elmokrif_cheque_company_id, elmokrif_cheque_number)",
         "Cheque numbers must be unique within a company."),
    ]

    @api.constrains("elmokrif_cheque_number", "company_id")
    def _check_cheque_number_unique(self):
        for payment in self.filtered("elmokrif_cheque_number"):
            duplicate = self.search_count([
                ("id", "!=", payment.id), ("company_id", "=", payment.company_id.id),
                ("elmokrif_cheque_number", "=", payment.elmokrif_cheque_number),
            ])
            if duplicate:
                raise UserError(_("Cheque numbers must be unique within a company."))

    def _workflow_write(self, values):
        return self.with_context(_elmokrif_cheque_workflow_token=_CHEQUE_WORKFLOW_TOKEN).write(values)

    def _ensure_cheque_manager(self):
        if not (self.env.su or self.env.user.has_group("account.group_account_manager")):
            raise AccessError(_("Only an Accounting Administrator can print or void a cheque."))

    @api.model_create_multi
    def create(self, values_list):
        cheque_fields = {
            "elmokrif_cheque_number", "elmokrif_cheque_state",
            "elmokrif_cheque_void_reason", "elmokrif_cheque_printed_at",
            "elmokrif_cheque_printed_by_id",
        }
        default_fields = {key[8:] for key in self.env.context if key.startswith("default_")}
        if cheque_fields.intersection(default_fields) or any(cheque_fields.intersection(values) for values in values_list):
            self._ensure_cheque_manager()
        workflow_fields = {
            "elmokrif_cheque_state", "elmokrif_cheque_printed_at",
            "elmokrif_cheque_printed_by_id",
        }
        in_workflow = self.env.context.get("_elmokrif_cheque_workflow_token") is _CHEQUE_WORKFLOW_TOKEN
        if not in_workflow and (workflow_fields.intersection(default_fields) or any(workflow_fields.intersection(values) for values in values_list)):
            raise UserError(_("Cheque workflow evidence is managed by the cheque actions."))
        return super().create(values_list)

    def write(self, values):
        payment_fields = {"amount", "currency_id", "payment_type", "partner_type", "partner_id", "journal_id", "company_id", "ref", "date", "move_id"}
        if payment_fields.intersection(values):
            if any(payment.elmokrif_cheque_state in ("printed", "void") for payment in self):
                raise UserError(_("A printed or voided cheque's payment details cannot be changed."))
        if (payment_fields | {"state"}).intersection(values):
            if self.env["elmokrif.bank.import.line"].sudo().search_count([
                ("matched_payment_id", "in", self.ids), ("state", "=", "matched"),
            ]):
                raise UserError(_("A payment matched to an imported bank line cannot be changed."))
        cheque_fields = {
            "elmokrif_cheque_number", "elmokrif_cheque_state", "elmokrif_cheque_void_reason",
            "elmokrif_cheque_printed_at", "elmokrif_cheque_printed_by_id",
        }
        in_workflow = self.env.context.get("_elmokrif_cheque_workflow_token") is _CHEQUE_WORKFLOW_TOKEN
        if cheque_fields.intersection(values):
            self._ensure_cheque_manager()
        if "elmokrif_cheque_number" in values and any(
            payment.elmokrif_cheque_state != "draft" for payment in self
        ):
            raise UserError(_("A printed or voided cheque number cannot be changed."))
        if "elmokrif_cheque_void_reason" in values and any(payment.elmokrif_cheque_state == "void" for payment in self):
            raise UserError(_("A voided cheque's recorded reason cannot be changed."))
        if {"elmokrif_cheque_state", "elmokrif_cheque_printed_at", "elmokrif_cheque_printed_by_id"}.intersection(values) and not in_workflow:
            raise UserError(_("Use the cheque workflow actions to change cheque print status."))
        return super().write(values)

    def action_mark_cheque_printed(self):
        self._ensure_cheque_manager()
        for payment in self:
            if not (payment.elmokrif_cheque_number or "").strip():
                raise UserError(_("Enter the cheque number before printing."))
            if payment.elmokrif_cheque_state == "void":
                raise UserError(_("A voided cheque cannot be printed."))
            if payment.elmokrif_cheque_state == "printed":
                raise UserError(_("This cheque has already been printed."))
            if payment.payment_type != "outbound" or payment.state != "posted":
                raise UserError(_("Only a posted outbound payment can be printed as a cheque."))
        self._workflow_write({
            "elmokrif_cheque_state": "printed", "elmokrif_cheque_printed_at": fields.Datetime.now(),
            "elmokrif_cheque_printed_by_id": self.env.user.id,
        })
        return self.env.ref("elmokrif_finance_operations.action_report_elmokrif_cheque").report_action(self)

    def action_void_cheque(self):
        self._ensure_cheque_manager()
        for payment in self:
            if payment.elmokrif_cheque_state != "printed":
                raise UserError(_("Only a printed cheque can be voided."))
            if not (payment.elmokrif_cheque_void_reason or "").strip():
                raise UserError(_("Record a reason before voiding a cheque."))
        self._workflow_write({"elmokrif_cheque_state": "void"})
        return True

    def unlink(self):
        if any(payment.elmokrif_cheque_state != "draft" for payment in self):
            raise UserError(_("Printed and voided cheques are retained as an audit trail."))
        return super().unlink()


class ChequeReport(models.AbstractModel):
    _name = "report.elmokrif_finance_operations.report_cheque"
    _description = "Validated EL MOKRIF Cheque Report"

    def _get_report_values(self, docids, data=None):
        payments = self.env["account.payment"].browse(docids)
        payments._ensure_cheque_manager()
        payments.check_access_rights("read")
        payments.check_access_rule("read")
        if not payments or any(
            payment.elmokrif_cheque_state != "printed"
            or payment.state != "posted"
            or payment.payment_type != "outbound"
            or not payment.elmokrif_cheque_number
            for payment in payments
        ):
            raise UserError(_("Print the cheque through its payment action before rendering this report."))
        return {"doc_ids": payments.ids, "doc_model": "account.payment", "docs": payments}
