import math

from odoo import _, api, fields, models
from odoo.exceptions import AccessError, ValidationError


ESTIMATION_WORKFLOW_TOKEN = object()

ESTIMATION_BASELINE_FIELDS = frozenset({
    "name", "chantier_id", "structure_type",
    "length", "width", "depth", "net_volume",
    "expansion_percent", "compaction_percent", "wastage_percent",
    "adjusted_volume", "cement_kg_per_m3", "bag_weight_kg", "sand_ratio",
    "gravel_ratio", "water_l_per_m3", "cement_kg", "cement_bags",
    "sand_volume", "gravel_volume", "water_litres", "cement_bag_cost",
    "sand_cost_m3", "gravel_cost_m3", "water_cost_litre",
    "labor_hourly_cost", "productivity_m3_per_day", "hours_per_day",
    "machinery_daily_cost", "truck_capacity_m3", "truck_trip_cost",
    "truck_trips", "labor_hours", "team_days", "material_cost",
    "labor_cost", "machinery_cost", "logistics_cost", "subtotal",
    "contingency_percent", "contingency_amount", "tax_id", "tax_amount",
    "total_cost", "foundation_percent", "superstructure_percent",
    "finishing_percent", "foundation_cost", "superstructure_cost",
    "finishing_cost",
})


class ChantierEstimation(models.Model):
    _name = "chantier.estimation"
    _description = "Chantier Quantity and Cost Estimate"
    _inherit = ["mail.thread", "mail.activity.mixin"]
    _order = "create_date desc, id desc"
    _check_company_auto = True

    name = fields.Char(required=True, default="New Estimate", tracking=True)
    state = fields.Selection([("draft", "Draft"), ("submitted", "Submitted"), ("approved", "Approved"), ("superseded", "Superseded")], default="draft", required=True, tracking=True, copy=False)
    revision_of_id = fields.Many2one(
        "chantier.estimation",
        string="Current approved baseline",
        copy=False,
        readonly=True,
    )
    approved_by_id = fields.Many2one("res.users", readonly=True, copy=False)
    approved_at = fields.Datetime(readonly=True, copy=False)
    variance_approved_by_id = fields.Many2one("res.users", readonly=True, copy=False)
    chantier_id = fields.Many2one(
        "project.project",
        required=True,
        check_company=True,
        domain="[('is_chantier', '=', True), ('company_id', 'in', allowed_company_ids)]",
        tracking=True,
    )
    company_id = fields.Many2one(related="chantier_id.company_id", store=True, readonly=True)
    currency_id = fields.Many2one(related="company_id.currency_id", readonly=True)
    structure_type = fields.Selection([
        ("concrete_slab", "Concrete slab"), ("strip_footing", "Strip footing"),
        ("excavation", "Excavation"), ("retaining_wall", "Retaining wall"),
        ("backfill", "Backfill / compaction"), ("other", "Other"),
    ], required=True, default="concrete_slab", tracking=True)
    length = fields.Float(required=True, digits=(16, 3), help="Metres")
    width = fields.Float(required=True, digits=(16, 3), help="Metres")
    depth = fields.Float(required=True, digits=(16, 3), string="Depth / Height", help="Metres")
    net_volume = fields.Float(compute="_compute_quantities", store=True, digits=(16, 3), string="Net volume (m³)")
    expansion_percent = fields.Float(default=0.0, string="Excavation expansion %", help="Foisonnement; normally 15–30% for excavated soil.")
    compaction_percent = fields.Float(default=0.0, string="Compaction allowance %", help="Tassement allowance for backfill or aggregate.")
    wastage_percent = fields.Float(default=5.0, string="Wastage / loss %")
    adjusted_volume = fields.Float(compute="_compute_quantities", store=True, digits=(16, 3), string="Procurement volume (m³)")
    cement_kg_per_m3 = fields.Float(default=350.0, string="Cement kg/m³")
    bag_weight_kg = fields.Float(default=50.0, string="Cement bag weight (kg)")
    sand_ratio = fields.Float(default=0.50, string="Sand m³ per m³")
    gravel_ratio = fields.Float(default=0.80, string="Gravel m³ per m³")
    water_l_per_m3 = fields.Float(default=175.0, string="Water L/m³")
    cement_kg = fields.Float(compute="_compute_quantities", store=True, digits=(16, 2))
    cement_bags = fields.Float(compute="_compute_quantities", store=True, digits=(16, 2))
    sand_volume = fields.Float(compute="_compute_quantities", store=True, digits=(16, 3), string="Sand (m³)")
    gravel_volume = fields.Float(compute="_compute_quantities", store=True, digits=(16, 3), string="Gravel (m³)")
    water_litres = fields.Float(compute="_compute_quantities", store=True, digits=(16, 1), string="Water (L)")
    cement_bag_cost = fields.Monetary(string="Cement / bag")
    sand_cost_m3 = fields.Monetary(string="Sand / m³")
    gravel_cost_m3 = fields.Monetary(string="Gravel / m³")
    water_cost_litre = fields.Monetary(string="Water / L")
    labor_hourly_cost = fields.Monetary(string="Labour / hour")
    productivity_m3_per_day = fields.Float(default=8.0, string="Team output m³ / day")
    hours_per_day = fields.Float(default=8.0, string="Hours / team day")
    machinery_daily_cost = fields.Monetary(string="Machinery / day")
    truck_capacity_m3 = fields.Float(default=10.0, string="Truck capacity (m³)")
    truck_trip_cost = fields.Monetary(string="Cost / truck trip")
    truck_trips = fields.Integer(compute="_compute_quantities", store=True)
    labor_hours = fields.Float(compute="_compute_quantities", store=True, digits=(16, 2))
    team_days = fields.Float(compute="_compute_quantities", store=True, digits=(16, 2))
    material_cost = fields.Monetary(compute="_compute_costs", store=True)
    labor_cost = fields.Monetary(compute="_compute_costs", store=True)
    machinery_cost = fields.Monetary(compute="_compute_costs", store=True)
    logistics_cost = fields.Monetary(compute="_compute_costs", store=True)
    subtotal = fields.Monetary(compute="_compute_costs", store=True)
    contingency_percent = fields.Float(default=5.0, string="Contingency %")
    contingency_amount = fields.Monetary(compute="_compute_costs", store=True)
    tax_id = fields.Many2one("account.tax", string="Tax / VAT", check_company=True, domain="[('company_id', '=', company_id)]")
    tax_amount = fields.Monetary(compute="_compute_costs", store=True)
    total_cost = fields.Monetary(compute="_compute_costs", store=True)
    foundation_percent = fields.Float(default=100.0, string="Foundation %")
    superstructure_percent = fields.Float(default=0.0, string="Superstructure %")
    finishing_percent = fields.Float(default=0.0, string="Finishing %")
    foundation_cost = fields.Monetary(compute="_compute_costs", store=True)
    superstructure_cost = fields.Monetary(compute="_compute_costs", store=True)
    finishing_cost = fields.Monetary(compute="_compute_costs", store=True)
    actual_labor_hours = fields.Float(string="Actual labour hours", tracking=True)
    actual_machinery_cost = fields.Monetary(string="Actual machinery cost", tracking=True)
    actual_other_cost = fields.Monetary(string="Actual other cost", tracking=True)
    manual_progress_percent = fields.Float(string="Manual progress %", tracking=True)
    task_count = fields.Integer(compute="_compute_live_control")
    completed_task_count = fields.Integer(compute="_compute_live_control")
    progress_percent = fields.Float(compute="_compute_live_control", string="Live progress %")
    actual_material_cost = fields.Monetary(compute="_compute_live_control", string="Actual stock valuation")
    actual_labor_cost = fields.Monetary(compute="_compute_live_control")
    actual_cost = fields.Monetary(compute="_compute_live_control", string="Actual cost")
    cost_variance = fields.Monetary(compute="_compute_live_control", string="Cost variance")
    budget_consumed_percent = fields.Float(compute="_compute_live_control", string="Budget consumed %")
    expected_cost_at_progress = fields.Monetary(compute="_compute_live_control", string="Expected cost at progress")
    schedule_variance_percent = fields.Float(compute="_compute_live_control", string="Cost consumption minus progress %")
    forecast_final_cost = fields.Monetary(compute="_compute_live_control", string="Forecast final cost")
    over_budget = fields.Boolean(compute="_compute_live_control")

    @api.depends("length", "width", "depth", "expansion_percent", "compaction_percent", "wastage_percent", "cement_kg_per_m3", "bag_weight_kg", "sand_ratio", "gravel_ratio", "water_l_per_m3", "productivity_m3_per_day", "hours_per_day", "truck_capacity_m3")
    def _compute_quantities(self):
        for item in self:
            item.net_volume = item.length * item.width * item.depth
            factor = (1 + item.expansion_percent / 100) * (1 + item.compaction_percent / 100) * (1 + item.wastage_percent / 100)
            item.adjusted_volume = item.net_volume * factor
            item.cement_kg = item.adjusted_volume * item.cement_kg_per_m3
            item.cement_bags = item.cement_kg / item.bag_weight_kg if item.bag_weight_kg else 0
            item.sand_volume = item.adjusted_volume * item.sand_ratio
            item.gravel_volume = item.adjusted_volume * item.gravel_ratio
            item.water_litres = item.adjusted_volume * item.water_l_per_m3
            item.truck_trips = math.ceil(item.adjusted_volume / item.truck_capacity_m3) if item.truck_capacity_m3 else 0
            item.team_days = item.adjusted_volume / item.productivity_m3_per_day if item.productivity_m3_per_day else 0
            item.labor_hours = item.team_days * item.hours_per_day

    @api.depends("cement_bags", "sand_volume", "gravel_volume", "water_litres", "cement_bag_cost", "sand_cost_m3", "gravel_cost_m3", "water_cost_litre", "labor_hours", "labor_hourly_cost", "team_days", "machinery_daily_cost", "truck_trips", "truck_trip_cost", "contingency_percent", "tax_id", "foundation_percent", "superstructure_percent", "finishing_percent")
    def _compute_costs(self):
        for item in self:
            item.material_cost = item.cement_bags * item.cement_bag_cost + item.sand_volume * item.sand_cost_m3 + item.gravel_volume * item.gravel_cost_m3 + item.water_litres * item.water_cost_litre
            item.labor_cost = item.labor_hours * item.labor_hourly_cost
            item.machinery_cost = item.team_days * item.machinery_daily_cost
            item.logistics_cost = item.truck_trips * item.truck_trip_cost
            item.subtotal = item.material_cost + item.labor_cost + item.machinery_cost + item.logistics_cost
            item.contingency_amount = item.subtotal * item.contingency_percent / 100
            taxable = item.subtotal + item.contingency_amount
            item.tax_amount = item.tax_id.compute_all(taxable, currency=item.currency_id, quantity=1)["total_included"] - taxable if item.tax_id else 0
            item.total_cost = taxable + item.tax_amount
            item.foundation_cost = item.total_cost * item.foundation_percent / 100
            item.superstructure_cost = item.total_cost * item.superstructure_percent / 100
            item.finishing_cost = item.total_cost * item.finishing_percent / 100

    @api.depends("chantier_id.material_cost", "chantier_id.task_ids.stage_id.fold", "actual_labor_hours", "labor_hourly_cost", "actual_machinery_cost", "actual_other_cost", "manual_progress_percent", "subtotal")
    def _compute_live_control(self):
        for item in self:
            tasks = item.chantier_id.task_ids
            item.task_count = len(tasks)
            item.completed_task_count = len(tasks.filtered(lambda task: task.stage_id.fold))
            item.progress_percent = item.completed_task_count * 100 / item.task_count if item.task_count else item.manual_progress_percent
            item.actual_material_cost = item.chantier_id.material_cost
            item.actual_labor_cost = item.actual_labor_hours * item.labor_hourly_cost
            item.actual_cost = item.actual_material_cost + item.actual_labor_cost + item.actual_machinery_cost + item.actual_other_cost
            item.cost_variance = item.actual_cost - item.subtotal
            item.budget_consumed_percent = item.actual_cost * 100 / item.subtotal if item.subtotal else 0
            item.expected_cost_at_progress = item.subtotal * item.progress_percent / 100
            item.schedule_variance_percent = item.budget_consumed_percent - item.progress_percent
            item.forecast_final_cost = item.actual_cost / item.progress_percent * 100 if item.progress_percent else item.actual_cost
            item.over_budget = item.forecast_final_cost > item.total_cost

    def _is_manager(self):
        return self.env.su or self.env.user.has_group("elmokrif_chantier.group_chantier_manager")

    @api.model_create_multi
    def create(self, vals_list):
        workflow_fields = {
            "state", "revision_of_id", "approved_by_id", "approved_at",
            "variance_approved_by_id",
        }
        if (
            any(
                workflow_fields.intersection(vals)
                and (
                    workflow_fields.intersection(vals) != {"state"}
                    or vals.get("state") != "draft"
                )
                for vals in vals_list
            )
            and self.env.context.get("_estimation_workflow_token") is not ESTIMATION_WORKFLOW_TOKEN
        ):
            raise AccessError(_("Estimate workflow evidence is managed by workflow actions."))
        return super().create(vals_list)

    def action_submit(self):
        if any(item.state != "draft" for item in self):
            raise ValidationError(_("Only draft estimates can be submitted."))
        self.with_context(_estimation_workflow_token=ESTIMATION_WORKFLOW_TOKEN).write({"state": "submitted"})

    def action_approve(self):
        if not self._is_manager():
            raise ValidationError(_("Only a chantier manager can approve an estimate."))
        for item in self:
            if item.state != "submitted":
                raise ValidationError(_("Only submitted estimates can be approved."))
            self.search([("chantier_id", "=", item.chantier_id.id), ("state", "=", "approved"), ("id", "!=", item.id)]).with_context(
                _estimation_workflow_token=ESTIMATION_WORKFLOW_TOKEN
            ).write({"state": "superseded"})
            item.with_context(_estimation_workflow_token=ESTIMATION_WORKFLOW_TOKEN).write({
                "state": "approved",
                "approved_by_id": self.env.user.id,
                "approved_at": fields.Datetime.now(),
            })

    def action_new_revision(self):
        self.ensure_one()
        if self.state != "approved":
            raise ValidationError(_("Create a revision from an approved estimate."))
        open_revision = self.search([
            ("revision_of_id", "=", self.id),
            ("state", "in", ("draft", "submitted")),
        ], limit=1)
        if open_revision:
            return open_revision._revision_form_action()
        values = self.copy_data({"state": "draft", "revision_of_id": self.id, "approved_by_id": False, "approved_at": False})[0]
        revision = self.with_context(_estimation_workflow_token=ESTIMATION_WORKFLOW_TOKEN).create(values)
        self.message_post(body=_("Draft revision %s was created.") % revision.display_name)
        return revision._revision_form_action()

    def _revision_form_action(self):
        self.ensure_one()
        return {
            "type": "ir.actions.act_window",
            "name": _("Estimate Revision"),
            "res_model": "chantier.estimation",
            "views": [(False, "form")],
            "res_id": self.id,
            "target": "current",
        }

    def action_approve_variance(self):
        if not self._is_manager():
            raise ValidationError(_("Only a chantier manager can approve a variance."))
        self.with_context(_estimation_workflow_token=ESTIMATION_WORKFLOW_TOKEN).write({
            "variance_approved_by_id": self.env.user.id,
        })

    def write(self, vals):
        workflow_fields = {
            "state", "revision_of_id", "approved_by_id", "approved_at",
            "variance_approved_by_id",
        }
        workflow_update_is_draft_save = (
            workflow_fields.intersection(vals) == {"state"}
            and vals.get("state") == "draft"
            and all(item.state == "draft" for item in self)
        )
        if (
            not workflow_update_is_draft_save
            and workflow_fields.intersection(vals)
            and self.env.context.get("_estimation_workflow_token") is not ESTIMATION_WORKFLOW_TOKEN
        ):
            raise AccessError(_("Estimate workflow evidence is managed by workflow actions."))
        if ESTIMATION_BASELINE_FIELDS.intersection(vals) and any(
            item.state in ("approved", "superseded") for item in self
        ):
            raise ValidationError(
                _("An approved or superseded estimate is immutable. Create a revision instead.")
            )
        return super().write(vals)

    @api.constrains("length", "width", "depth", "wastage_percent", "expansion_percent", "compaction_percent", "productivity_m3_per_day", "hours_per_day", "truck_capacity_m3", "foundation_percent", "superstructure_percent", "finishing_percent")
    def _check_values(self):
        for item in self:
            if min(item.length, item.width, item.depth) <= 0:
                raise ValidationError(_("Length, width, and depth must be greater than zero."))
            if min(item.wastage_percent, item.expansion_percent, item.compaction_percent) < 0:
                raise ValidationError(_("Allowances cannot be negative."))
            if item.productivity_m3_per_day <= 0 or item.hours_per_day <= 0 or item.truck_capacity_m3 <= 0:
                raise ValidationError(_("Productivity, hours per day, and truck capacity must be greater than zero."))
            if not math.isclose(item.foundation_percent + item.superstructure_percent + item.finishing_percent, 100.0, abs_tol=0.01):
                raise ValidationError(_("Project phase percentages must total 100%."))
            if not 0 <= item.manual_progress_percent <= 100:
                raise ValidationError(_("Manual progress must be between 0 and 100%."))
