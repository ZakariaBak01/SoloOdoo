from odoo import _, api, fields, models
from odoo.exceptions import UserError


class AccountMove(models.Model):
    _inherit = "account.move"

    chantier_finance_readiness_state = fields.Selection(
        [("missing", "Not Configured"), ("draft", "Not Approved"), ("approved", "Approved")],
        compute="_compute_chantier_finance_readiness_state",
    )

    @api.depends("company_id", "chantier_id", "invoice_line_ids.chantier_id")
    def _compute_chantier_finance_readiness_state(self):
        Readiness = self.env["chantier.finance.readiness"].sudo()
        for move in self:
            if not (move.chantier_id or move.invoice_line_ids.mapped("chantier_id")):
                move.chantier_finance_readiness_state = "approved"
                continue
            readiness = Readiness.search([("company_id", "=", move.company_id.id)], limit=1)
            move.chantier_finance_readiness_state = readiness.state if readiness else "missing"

    def _post(self, soft=True):
        Readiness = self.env["chantier.finance.readiness"].sudo()
        for move in self.filtered(lambda item: item.state == "draft" and item.is_invoice(include_receipts=True)):
            if not (move.chantier_id or move.invoice_line_ids.mapped("chantier_id")):
                continue
            readiness = Readiness.search([("company_id", "=", move.company_id.id)], limit=1)
            if not readiness or readiness.state != "approved":
                raise UserError(_(
                    "This chantier financial document cannot be posted until an Accounting "
                    "Administrator completes and approves Finance Readiness for %(company)s.",
                    company=move.company_id.display_name,
                ))
        return super()._post(soft=soft)
