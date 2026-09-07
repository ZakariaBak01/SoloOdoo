from datetime import timedelta

from odoo import _, api, fields, models
from odoo.exceptions import UserError, ValidationError
from .utils import chantier_analytic_distribution, validate_chantier_link


class SaleOrder(models.Model):
    _inherit = "sale.order"

    chantier_id = fields.Many2one(
        "project.project",
        string="Chantier",
        copy=True,
        check_company=True,
        ondelete="restrict",
        default=lambda self: self._default_chantier(),
        domain="[('is_chantier', '=', True), ('company_id', '=', company_id)]",
        tracking=True,
    )
    chantier_first_sent_at = fields.Datetime(
        string="First Sent At",
        copy=False,
        readonly=True,
    )
    chantier_followup_activity_id = fields.Many2one(
        "mail.activity",
        string="Chantier Follow-up",
        copy=False,
        readonly=True,
        ondelete="set null",
    )

    @api.model
    def _default_chantier(self):
        explicit = self.env.context.get("default_chantier_id")
        if explicit:
            chantier = self.env["project.project"].browse(explicit).exists()
            if chantier:
                return chantier
        partner_id = self.env.context.get("default_partner_id")
        if not partner_id:
            return self.env["project.project"]
        partner = self.env["res.partner"].browse(partner_id).exists()
        if not partner:
            return self.env["project.project"]
        return self._find_chantier_for_partner(partner, self.env.company)

    @api.model
    def _find_chantier_for_partner(self, partner, company):
        if partner.default_chantier_id:
            return partner.default_chantier_id
        partner_ids = self.env["res.partner"].search(
            [("commercial_partner_id", "=", partner.commercial_partner_id.id)]
        ).ids
        candidates = self.env["project.project"].search(
            [
                ("is_chantier", "=", True),
                ("company_id", "=", company.id),
                ("site_partner_id", "in", partner_ids),
            ],
            limit=2,
        )
        return candidates if len(candidates) == 1 else self.env["project.project"]

    @api.model_create_multi
    def create(self, vals_list):
        for vals in vals_list:
            if not vals.get("chantier_id") and vals.get("partner_id"):
                partner = self.env["res.partner"].browse(vals["partner_id"]).exists()
                company = self.env["res.company"].browse(
                    vals.get("company_id")
                ) or self.env.company
                if partner:
                    chantier = self._find_chantier_for_partner(partner, company)
                    if chantier:
                        vals["chantier_id"] = chantier.id
            if vals.get("order_line") and not vals.get("chantier_id"):
                for command in vals["order_line"]:
                    if command[0] == 0 and isinstance(command[2], dict):
                        vals.setdefault("chantier_id", command[2].get("chantier_id"))
                        if vals.get("chantier_id"):
                            break
        orders = super().create(vals_list)
        for order in orders:
            order._validate_all_chantier_links()
        return orders

    def write(self, vals):
        changing_chantier = "chantier_id" in vals
        old_chantiers = {order.id: order.chantier_id.id for order in self}
        if changing_chantier:
            for order in self:
                if order.state not in ("draft", "sent") and order.chantier_id.id != vals["chantier_id"]:
                    raise UserError(_("The chantier cannot be changed on a confirmed order."))
        result = super().write(vals)
        if changing_chantier:
            for order in self.filtered(lambda item: item.state in ("draft", "sent")):
                order.order_line.filtered(
                    lambda line: not line.chantier_id
                    or line.chantier_id.id == old_chantiers.get(order.id)
                ).write({"chantier_id": vals["chantier_id"]})
        self._validate_all_chantier_links()
        if vals.get("state") == "sent":
            self._schedule_first_chantier_followup()
        return result

    @api.onchange("partner_id")
    def _onchange_partner_chantier(self):
        for order in self:
            if not order.partner_id:
                order.chantier_id = False
                continue
            if not order.chantier_id or order.chantier_id.site_partner_id.commercial_partner_id != order.partner_id.commercial_partner_id:
                order.chantier_id = self._find_chantier_for_partner(
                    order.partner_id, order.company_id or self.env.company
                )

    @api.constrains("chantier_id", "partner_id", "company_id")
    def _check_chantier_link(self):
        self._validate_all_chantier_links()

    def _linked_chantiers(self):
        self.ensure_one()
        return (self.mapped("chantier_id") | self.order_line.mapped("chantier_id")).filtered(
            lambda chantier: chantier.is_chantier
        )

    def _validate_all_chantier_links(self):
        for order in self:
            for chantier in order._linked_chantiers():
                validate_chantier_link(chantier, order.company_id, order.partner_id)

    def _ensure_chantier_commitments_ready(self):
        for order in self:
            chantiers = order._linked_chantiers()
            if not chantiers:
                raise UserError(_("A chantier is required before confirming the order."))
            order._validate_all_chantier_links()
            for chantier in chantiers:
                if not chantier.chantier_initialized:
                    raise UserError(
                        _(
                            "Initialize chantier %(chantier)s before confirming this order.",
                            chantier=chantier.display_name,
                        )
                    )
                chantier._ensure_chantier_accepts_commitments()

    def action_initialize_linked_chantiers(self):
        self._validate_all_chantier_links()
        chantiers = self.mapped(lambda order: order._linked_chantiers())
        if not chantiers:
            raise UserError(_("Link a chantier before initializing it."))
        chantiers.sorted("id").action_initialize_chantier()
        return True

    def _prepare_invoice(self):
        vals = super()._prepare_invoice()
        linked = self._linked_chantiers()
        if len(linked) == 1:
            vals["chantier_id"] = linked.id
        return vals

    def action_confirm(self):
        self._ensure_chantier_commitments_ready()
        for order in self:
            order.order_line._apply_chantier_analytic_distribution()
        result = super().action_confirm()
        self._clear_chantier_followup_activity()
        return result

    def action_cancel(self):
        result = super().action_cancel()
        self._clear_chantier_followup_activity()
        return result

    def action_quotation_send(self):
        result = super().action_quotation_send()
        self._schedule_first_chantier_followup()
        return result

    def _schedule_first_chantier_followup(self):
        Activity = self.env["mail.activity"]
        for order in self.filtered(
            lambda item: item.state == "sent"
            and item._linked_chantiers()
            and not item.chantier_first_sent_at
        ):
            company = order.company_id
            activity_type = (
                company.sale_chantier_followup_activity_type_id
                or self.env.ref("mail.mail_activity_data_todo", raise_if_not_found=True)
            )
            existing = Activity.search(
                [
                    ("res_model", "=", "sale.order"),
                    ("res_id", "=", order.id),
                    ("is_chantier_followup", "=", True),
                    ("date_done", "=", False),
                ],
                limit=1,
            )
            if existing:
                activity = existing
            else:
                activity = order.activity_schedule(
                    activity_type_id=activity_type.id,
                    date_deadline=fields.Date.today()
                    + timedelta(days=company.sale_chantier_followup_delay_days),
                    user_id=order.user_id.id or self.env.user.id,
                    summary=_("Chantier quotation follow-up"),
                    note=_("Follow up this chantier quotation with the customer."),
                )
                activity.write({"is_chantier_followup": True})
            order.write(
                {
                    "chantier_first_sent_at": fields.Datetime.now(),
                    "chantier_followup_activity_id": activity.id,
                }
            )

    def _clear_chantier_followup_activity(self):
        activities = self.env["mail.activity"].search(
            [
                ("res_model", "=", "sale.order"),
                ("res_id", "in", self.ids),
                ("is_chantier_followup", "=", True),
                ("date_done", "=", False),
            ]
        )
        if activities:
            activities.unlink()
        self.write({"chantier_followup_activity_id": False})


class SaleOrderLine(models.Model):
    _inherit = "sale.order.line"

    chantier_id = fields.Many2one(
        "project.project",
        string="Chantier",
        copy=True,
        check_company=True,
        ondelete="restrict",
        domain="[('is_chantier', '=', True), ('company_id', '=', company_id)]",
    )
    sale_chantier_analytic_distribution = fields.Json(
        string="Chantier Analytic Allocation",
        compute="_compute_sale_chantier_analytic_distribution",
    )

    @api.depends("chantier_id", "chantier_id.analytic_account_id")
    def _compute_sale_chantier_analytic_distribution(self):
        for line in self:
            line.sale_chantier_analytic_distribution = chantier_analytic_distribution(
                line.chantier_id
            )

    @api.model_create_multi
    def create(self, vals_list):
        for vals in vals_list:
            order = self.env["sale.order"].browse(vals.get("order_id")).exists()
            if order and not vals.get("chantier_id") and order.chantier_id:
                vals["chantier_id"] = order.chantier_id.id
        lines = super().create(vals_list)
        lines._validate_chantier_links()
        lines._apply_chantier_analytic_distribution()
        return lines

    def write(self, vals):
        if "chantier_id" in vals:
            for line in self:
                if line.order_id.state not in ("draft", "sent") and line.chantier_id.id != vals["chantier_id"]:
                    raise UserError(_("The chantier cannot be changed on a confirmed order line."))
        result = super().write(vals)
        self._validate_chantier_links()
        if "chantier_id" in vals:
            self._apply_chantier_analytic_distribution()
        return result

    @api.onchange("order_id")
    def _onchange_order_chantier(self):
        for line in self:
            if line.order_id and not line.chantier_id:
                line.chantier_id = line.order_id.chantier_id

    @api.constrains("chantier_id", "order_id", "company_id")
    def _check_chantier_link(self):
        self._validate_chantier_links()

    def _validate_chantier_links(self):
        for line in self:
            if line.chantier_id:
                validate_chantier_link(
                    line.chantier_id,
                    line.order_id.company_id,
                    line.order_id.partner_id,
                )

    def _apply_chantier_analytic_distribution(self):
        if "analytic_distribution" not in self._fields:
            return
        for line in self:
            distribution = chantier_analytic_distribution(line.chantier_id)
            if distribution:
                line.analytic_distribution = distribution

    def _prepare_invoice_line(self, **optional_values):
        vals = super()._prepare_invoice_line(**optional_values)
        if self.chantier_id:
            vals.update(
                {
                    "chantier_id": self.chantier_id.id,
                    "chantier_origin_id": self.chantier_id.id,
                    "sale_line_id": self.id,
                }
            )
            distribution = chantier_analytic_distribution(self.chantier_id)
            if distribution:
                vals["analytic_distribution"] = distribution
        return vals
