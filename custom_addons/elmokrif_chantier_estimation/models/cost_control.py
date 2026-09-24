import math

from odoo import _, api, fields, models
from odoo.exceptions import ValidationError


class ChantierCostCode(models.Model):
    _name = "chantier.cost.code"
    _description = "Chantier Cost Code"
    _order = "code"
    _check_company_auto = True

    code = fields.Char(required=True)
    name = fields.Char(required=True)
    company_id = fields.Many2one("res.company", check_company=True)
    active = fields.Boolean(default=True)
    _sql_constraints = [("chantier_cost_code_unique", "unique(code, company_id)", "A cost code must be unique per company.")]


class ChantierDailyReport(models.Model):
    _name = "chantier.daily.report"
    _description = "Chantier Daily Report"
    _inherit = ["mail.thread", "mail.activity.mixin"]
    _order = "report_date desc, id desc"
    _check_company_auto = True

    chantier_id = fields.Many2one("project.project", required=True, domain="[('is_chantier', '=', True)]")
    company_id = fields.Many2one(related="chantier_id.company_id", store=True, readonly=True)
    report_date = fields.Date(required=True, default=fields.Date.today)
    cost_code_id = fields.Many2one("chantier.cost.code")
    work_quantity = fields.Float(string="Completed quantity")
    work_unit = fields.Char(default="m³")
    labor_hours = fields.Float()
    equipment_hours = fields.Float()
    equipment_cost = fields.Monetary(currency_field="currency_id")
    other_cost = fields.Monetary(currency_field="currency_id")
    weather = fields.Selection([("sunny", "Sunny"), ("rain", "Rain"), ("wind", "Wind"), ("other", "Other")])
    blockers = fields.Text()
    note = fields.Text()
    attachment_ids = fields.Many2many("ir.attachment", "chantier_daily_report_attachment_rel", "report_id", "attachment_id", string="Photos and evidence")
    currency_id = fields.Many2one(related="company_id.currency_id", readonly=True)

    @api.constrains(
        "work_quantity",
        "labor_hours",
        "equipment_hours",
        "equipment_cost",
        "other_cost",
    )
    def _check_nonnegative_values(self):
        labels = {
            "work_quantity": _("Completed quantity"),
            "labor_hours": _("Labour hours"),
            "equipment_hours": _("Equipment hours"),
            "equipment_cost": _("Equipment cost"),
            "other_cost": _("Other cost"),
        }
        for report in self:
            for field_name, label in labels.items():
                value = report[field_name]
                if not math.isfinite(value) or value < 0:
                    raise ValidationError(
                        _("%(field)s must be zero or greater.", field=label)
                    )


class ProjectProject(models.Model):
    _inherit = "project.project"

    daily_report_ids = fields.One2many("chantier.daily.report", "chantier_id")
    actual_cost_live = fields.Monetary(compute="_compute_chantier_control", currency_field="currency_id")
    approved_budget_live = fields.Monetary(compute="_compute_chantier_control", currency_field="currency_id")
    revenue_invoiced_live = fields.Monetary(compute="_compute_chantier_control", currency_field="currency_id")
    margin_forecast_live = fields.Monetary(compute="_compute_chantier_control", currency_field="currency_id")

    def _compute_chantier_control(self):
        Estimate = self.env["chantier.estimation"]
        Move = self.env["account.move.line"]
        for chantier in self:
            estimate = Estimate.search([("chantier_id", "=", chantier.id), ("state", "=", "approved")], limit=1)
            chantier.approved_budget_live = estimate.total_cost if estimate else 0
            chantier.actual_cost_live = estimate.actual_cost if estimate else chantier.material_cost
            lines = Move.search([("chantier_id", "=", chantier.id), ("move_id.state", "=", "posted"), ("move_id.move_type", "=", "out_invoice")])
            chantier.revenue_invoiced_live = sum(lines.mapped("price_subtotal"))
            chantier.margin_forecast_live = chantier.revenue_invoiced_live - chantier.actual_cost_live


class StockMove(models.Model):
    _inherit = "stock.move"
    cost_code_id = fields.Many2one("chantier.cost.code", check_company=True)

class PurchaseOrderLine(models.Model):
    _inherit = "purchase.order.line"
    cost_code_id = fields.Many2one("chantier.cost.code", check_company=True)

class SaleOrderLine(models.Model):
    _inherit = "sale.order.line"
    cost_code_id = fields.Many2one("chantier.cost.code", check_company=True)

class AccountMoveLine(models.Model):
    _inherit = "account.move.line"
    cost_code_id = fields.Many2one("chantier.cost.code", check_company=True)
