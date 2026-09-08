from odoo import _, api, fields, models
from odoo.exceptions import AccessError, UserError

from .consumption import _CONSUMPTION_WORKFLOW_TOKEN


class StockPicking(models.Model):
    _inherit = "stock.picking"

    chantier_consumption_id = fields.Many2one(
        "chantier.material.consumption", string="Approved Consumption", readonly=True,
        copy=False, ondelete="restrict", check_company=True,
    )

    @api.model_create_multi
    def create(self, values_list):
        if (any(values.get("chantier_consumption_id") for values in values_list) or self.env.context.get("default_chantier_consumption_id")) and (
            self.env.context.get("_elmokrif_consumption_workflow_token") is not _CONSUMPTION_WORKFLOW_TOKEN
        ):
            raise UserError(_("Approved consumption links are managed by the consumption workflow."))
        return super().create(values_list)

    def write(self, values):
        if "chantier_consumption_id" in values and (
            self.env.context.get("_elmokrif_consumption_workflow_token") is not _CONSUMPTION_WORKFLOW_TOKEN
        ):
            raise UserError(_("Approved consumption links are managed by the consumption workflow."))
        return super().write(values)

    def _check_approved_consumption(self):
        for picking in self:
            operations = picking.move_ids.filtered(lambda move: move.state != "cancel")
            sources = operations.location_id | operations.move_line_ids.location_id
            destinations = operations.location_dest_id | operations.move_line_ids.location_dest_id
            warehouses = self.env["stock.warehouse"].search([("company_id", "=", picking.company_id.id)])
            consumption_roots = warehouses.chantier_consumption_location_id
            site_roots = self.env["stock.location"].search([("chantier_id", "!=", False), ("company_id", "=", picking.company_id.id)])
            physical_consumption = bool(
                consumption_roots and site_roots
                and self.env["stock.location"].search_count([("id", "in", sources.ids), ("id", "child_of", site_roots.ids)])
                and self.env["stock.location"].search_count([("id", "in", destinations.ids), ("id", "child_of", consumption_roots.ids)])
            )
            if (
                (picking.chantier_operation == "consumption" or physical_consumption)
                and picking.company_id.chantier_consumption_control_required
                and not picking.chantier_consumption_id
            ):
                raise UserError(_(
                    "Create an Approved Consumption record before validating chantier material consumption."
                ))
            if picking.chantier_consumption_id and self.env.context.get("_elmokrif_consumption_workflow_token") is not _CONSUMPTION_WORKFLOW_TOKEN:
                raise AccessError(_("Approved consumption stock transfers are completed by the approval action."))

    def _action_done(self):
        self._check_approved_consumption()
        return super()._action_done()

    def button_validate(self):
        self._check_approved_consumption()
        result = super().button_validate()
        for picking in self.filtered("chantier_consumption_id"):
            for move in picking.move_ids.filtered(lambda item: item.state == "done"):
                line = move.chantier_consumption_line_id
                if line:
                    line.sudo().with_context(
                        _elmokrif_consumption_workflow_token=_CONSUMPTION_WORKFLOW_TOKEN
                    ).write({"stock_move_id": move.id})
        return result


class StockMove(models.Model):
    _inherit = "stock.move"

    chantier_consumption_line_id = fields.Many2one(
        "chantier.material.consumption.line", string="Consumption Line", readonly=True,
        copy=False, ondelete="restrict", check_company=True,
    )

    @api.model_create_multi
    def create(self, vals_list):
        if self.env.context.get("_elmokrif_consumption_workflow_token") is not _CONSUMPTION_WORKFLOW_TOKEN and any(
            values.get("chantier_consumption_line_id") or self.env.context.get("default_chantier_consumption_line_id")
            for values in vals_list
        ):
            raise AccessError(_("Consumption stock links are managed by the approval workflow."))
        return super().create(vals_list)

    def write(self, values):
        if "chantier_consumption_line_id" in values and self.env.context.get("_elmokrif_consumption_workflow_token") is not _CONSUMPTION_WORKFLOW_TOKEN:
            raise AccessError(_("Consumption stock links are managed by the approval workflow."))
        return super().write(values)

    @api.model
    def _prepare_merge_moves_distinct_fields(self):
        return [*super()._prepare_merge_moves_distinct_fields(), "chantier_consumption_line_id"]
