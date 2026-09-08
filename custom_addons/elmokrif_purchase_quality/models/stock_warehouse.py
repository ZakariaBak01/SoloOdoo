from odoo import _, fields, models


class StockWarehouse(models.Model):
    _inherit = "stock.warehouse"

    chantier_input_location_id = fields.Many2one(
        "stock.location",
        string="Chantier Input Location",
        copy=False,
        check_company=True,
        domain="[('usage', '=', 'internal'), ('company_id', '=', company_id)]",
    )
    chantier_quality_location_id = fields.Many2one(
        "stock.location",
        string="Chantier Quality Location",
        copy=False,
        check_company=True,
        domain="[('usage', '=', 'internal'), ('company_id', '=', company_id)]",
    )
    chantier_quarantine_location_id = fields.Many2one(
        "stock.location",
        string="Chantier Quarantine Location",
        copy=False,
        check_company=True,
        domain="[('usage', '=', 'internal'), ('company_id', '=', company_id)]",
    )

    def _ensure_chantier_quality_locations(self):
        for warehouse in self:
            values = {}
            for field_name, location_name in (
                ("chantier_input_location_id", _("Input")),
                ("chantier_quality_location_id", _("Quality")),
                ("chantier_quarantine_location_id", _("Quarantine")),
            ):
                location = warehouse[field_name]
                if not location:
                    location = self.env["stock.location"].sudo().create({
                        "name": location_name,
                        "location_id": warehouse.view_location_id.id,
                        "usage": "internal",
                        "company_id": warehouse.company_id.id,
                    })
                    values[field_name] = location.id
            if values:
                warehouse.sudo().write(values)
        return True
