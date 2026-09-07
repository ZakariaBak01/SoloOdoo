from odoo import _, api, fields, models
from odoo.exceptions import UserError


class StockPicking(models.Model):
    _inherit = "stock.picking"

    chantier_id = fields.Many2one("project.project", string="Chantier", copy=True, check_company=True)
    material_request_id = fields.Many2one("chantier.material.request", string="Material Request", copy=True, readonly=True, check_company=True)
    chantier_operation = fields.Selection([
        ("delivery", "Delivery to Site"),
        ("consumption", "Consumption"),
        ("return", "Return to Warehouse"),
        ("missing", "Missing Material"),
    ], string="Chantier Material Operation", default="delivery", tracking=True)

    def _get_chantier_loss_location(self, company):
        """Return the company's inventory-adjustment location for site losses."""
        location = self.env["stock.location"].search(
            [
                ("usage", "=", "inventory"),
                "|",
                ("company_id", "=", False),
                ("company_id", "=", company.id),
            ],
            limit=1,
        )
        if not location:
            raise UserError(
                _("Create an inventory adjustment location before recording material consumption or loss.")
            )
        return location

    @api.onchange("chantier_id", "chantier_operation")
    def _onchange_chantier_operation(self):
        for picking in self.filtered("chantier_id"):
            chantier = picking.chantier_id
            if picking.chantier_operation == "delivery":
                picking.location_id = chantier.warehouse_id.lot_stock_id
                picking.location_dest_id = chantier.site_location_id
            elif picking.chantier_operation == "return":
                picking.location_id = chantier.site_location_id
                picking.location_dest_id = chantier.warehouse_id.lot_stock_id
            else:
                loss_location = picking._get_chantier_loss_location(chantier.company_id)
                picking.location_id = chantier.site_location_id
                picking.location_dest_id = loss_location

    @api.constrains("chantier_id", "chantier_operation", "location_id", "location_dest_id")
    def _check_chantier_operation_locations(self):
        for picking in self.filtered("chantier_id"):
            chantier = picking.chantier_id
            loss_location = picking._get_chantier_loss_location(chantier.company_id)
            expected = {
                "delivery": (chantier.warehouse_id.lot_stock_id, chantier.site_location_id),
                "return": (chantier.site_location_id, chantier.warehouse_id.lot_stock_id),
                "consumption": (chantier.site_location_id, loss_location),
                "missing": (chantier.site_location_id, loss_location),
            }[picking.chantier_operation]
            if picking.location_id != expected[0] or picking.location_dest_id != expected[1]:
                raise UserError(_("The locations do not match the selected chantier material operation."))

    def _action_done(self):
        result = super()._action_done()
        self.mapped("material_request_id")._update_delivery_state()
        return result
