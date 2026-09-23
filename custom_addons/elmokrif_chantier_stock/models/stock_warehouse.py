from odoo import _, fields, models


class StockWarehouse(models.Model):
    _inherit = "stock.warehouse"

    chantier_consumption_location_id = fields.Many2one(
        "stock.location",
        string="Chantier Consumption Location",
        copy=False,
        readonly=True,
        check_company=True,
        domain="[('usage', '=', 'inventory'), ('company_id', '=', company_id)]",
    )
    chantier_missing_location_id = fields.Many2one(
        "stock.location",
        string="Chantier Missing Material Location",
        copy=False,
        readonly=True,
        check_company=True,
        domain="[('usage', '=', 'inventory'), ('company_id', '=', company_id)]",
    )

    def _ensure_chantier_operation_locations(self):
        """Create dedicated valuation destinations instead of using a generic loss bin."""
        for warehouse in self:
            if warehouse.int_type_id and not warehouse.int_type_id.active:
                warehouse.int_type_id.sudo().active = True
            values = {}
            for field_name, location_name in (
                ("chantier_consumption_location_id", _("Chantier Consumption")),
                ("chantier_missing_location_id", _("Chantier Missing Material")),
            ):
                location = warehouse[field_name]
                if not location:
                    location = self.env["stock.location"].sudo().search([
                        ("name", "=", location_name),
                        ("location_id", "=", warehouse.view_location_id.id),
                        ("usage", "=", "inventory"),
                        ("company_id", "=", warehouse.company_id.id),
                    ], limit=1)
                if not location:
                    location = self.env["stock.location"].sudo().create({
                        "name": location_name,
                        "location_id": warehouse.view_location_id.id,
                        "usage": "inventory",
                        "company_id": warehouse.company_id.id,
                    })
                if warehouse[field_name] != location:
                    values[field_name] = location.id
            if values:
                warehouse.sudo().write(values)
        return True
