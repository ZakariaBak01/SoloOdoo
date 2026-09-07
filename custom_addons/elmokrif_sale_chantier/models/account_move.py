from odoo import _, api, fields, models
from odoo.exceptions import UserError

from .utils import chantier_analytic_distribution, validate_chantier_link


class AccountMove(models.Model):
    _inherit = "account.move"

    chantier_id = fields.Many2one(
        "project.project",
        string="Chantier",
        copy=True,
        check_company=True,
        ondelete="restrict",
        domain="[('is_chantier', '=', True), ('company_id', '=', company_id)]",
        tracking=True,
    )

    @api.constrains("chantier_id", "partner_id", "company_id")
    def _check_chantier_link(self):
        for move in self:
            validate_chantier_link(move.chantier_id, move.company_id, move.partner_id)

    def write(self, vals):
        if "chantier_id" in vals:
            for move in self:
                if move.state == "posted" and move.chantier_id.id != vals["chantier_id"]:
                    raise UserError(_("The chantier cannot be changed on a posted invoice."))
        result = super().write(vals)
        for move in self:
            validate_chantier_link(move.chantier_id, move.company_id, move.partner_id)
        return result


class AccountMoveLine(models.Model):
    _inherit = "account.move.line"

    chantier_id = fields.Many2one(
        "project.project",
        string="Chantier",
        copy=True,
        check_company=True,
        ondelete="restrict",
        domain="[('is_chantier', '=', True), ('company_id', '=', company_id)]",
        index=True,
    )
    chantier_origin_id = fields.Many2one(
        "project.project",
        string="Chantier Origin",
        related="chantier_id",
        store=True,
        readonly=True,
        copy=True,
    )
    sale_line_id = fields.Many2one(
        "sale.order.line",
        string="Sales Order Line",
        copy=True,
        ondelete="set null",
        index=True,
    )

    @api.model_create_multi
    def create(self, vals_list):
        for vals in vals_list:
            move = self.env["account.move"].browse(vals.get("move_id")).exists()
            if move and not vals.get("chantier_id") and move.chantier_id:
                vals["chantier_id"] = move.chantier_id.id
            if vals.get("chantier_id") and not vals.get("analytic_distribution"):
                chantier = self.env["project.project"].browse(vals["chantier_id"]).exists()
                if chantier:
                    vals["analytic_distribution"] = chantier_analytic_distribution(chantier)
        lines = super().create(vals_list)
        lines._validate_chantier_links()
        return lines

    def write(self, vals):
        if "chantier_id" in vals:
            for line in self:
                if line.move_id.state == "posted" and line.chantier_id.id != vals["chantier_id"]:
                    raise UserError(
                        _("The chantier cannot be changed on a posted invoice line.")
                    )
        result = super().write(vals)
        self._validate_chantier_links()
        return result

    @api.constrains("chantier_id", "move_id", "partner_id", "company_id")
    def _check_chantier_link(self):
        self._validate_chantier_links()

    def _validate_chantier_links(self):
        for line in self:
            move = line.move_id
            if line.chantier_id and move:
                validate_chantier_link(
                    line.chantier_id,
                    move.company_id,
                    move.partner_id or line.partner_id,
                )
