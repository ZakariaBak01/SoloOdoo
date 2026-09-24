from odoo import _, api, fields, models
from odoo.exceptions import AccessError, UserError


class AccountMove(models.Model):
    _inherit = "account.move"

    elmokrif_collection_hold = fields.Boolean(string="Collection Hold", copy=False, tracking=True)
    elmokrif_collection_hold_reason = fields.Text(string="Collection Hold / Dispute Reason", copy=False, tracking=True)
    elmokrif_collector_id = fields.Many2one("res.users", string="Collector", tracking=True)
    elmokrif_reminder_ids = fields.One2many(
        "elmokrif.payment.reminder", "invoice_id", string="Payment Reminders", readonly=True,
    )
    elmokrif_reminder_count = fields.Integer(
        string="Payment Reminder Count", compute="_compute_elmokrif_reminder_count",
    )

    @api.depends("elmokrif_reminder_ids")
    def _compute_elmokrif_reminder_count(self):
        for move in self:
            move.elmokrif_reminder_count = len(move.elmokrif_reminder_ids)

    def action_view_elmokrif_reminders(self):
        self.ensure_one()
        action = self.env["ir.actions.actions"]._for_xml_id(
            "elmokrif_finance_operations.action_elmokrif_payment_reminder"
        )
        action["domain"] = [("invoice_id", "=", self.id)]
        action["context"] = {"default_invoice_id": self.id}
        return action

    @api.model_create_multi
    def create(self, values_list):
        if any(values.get("elmokrif_collection_hold", self.env.context.get("default_elmokrif_collection_hold")) for values in values_list):
            raise UserError(_("A collection hold can only be added to an existing posted customer invoice."))
        return super().create(values_list)

    def write(self, values):
        if "elmokrif_collection_hold" in values:
            placing_hold = bool(values["elmokrif_collection_hold"])
            for move in self:
                if placing_hold:
                    if move.move_type != "out_invoice" or move.state != "posted":
                        raise UserError(_("A collection hold can only be set on a posted customer invoice."))
                    if not (values.get("elmokrif_collection_hold_reason", move.elmokrif_collection_hold_reason) or "").strip():
                        raise UserError(_("Enter the dispute or hold reason before placing the invoice on hold."))
                elif not (self.env.su or self.env.user.has_group("account.group_account_manager")):
                    raise AccessError(_("Only an Accounting Administrator can release a collection hold."))
        if (
            "elmokrif_collection_hold_reason" in values
            and any(move.elmokrif_collection_hold for move in self)
            and values.get("elmokrif_collection_hold", True)
        ):
            raise UserError(_("Release the collection hold before changing its recorded reason."))
        return super().write(values)

    def action_set_collection_hold(self):
        self.write({"elmokrif_collection_hold": True})
        return True

    def action_release_collection_hold(self):
        if not self.env.user.has_group("account.group_account_manager"):
            raise AccessError(_("Only an Accounting Administrator can release a collection hold."))
        self.write({"elmokrif_collection_hold": False, "elmokrif_collection_hold_reason": False})
        return True
