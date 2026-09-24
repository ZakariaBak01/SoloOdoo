from datetime import timedelta

from odoo import _, api, fields, models


class ElMokrifDashboard(models.Model):
    _name = "elmokrif.dashboard"
    _description = "EL MOKRIF Management Dashboard"
    _check_company_auto = True

    company_id = fields.Many2one(
        "res.company", required=True, default=lambda self: self.env.company,
    )
    as_of_date = fields.Date(required=True, default=fields.Date.context_today)
    currency_id = fields.Many2one(related="company_id.currency_id", readonly=True)
    monthly_revenue = fields.Monetary(compute="_compute_kpis", currency_field="currency_id")
    unpaid_over_30 = fields.Monetary(compute="_compute_kpis", currency_field="currency_id")
    quotation_conversion = fields.Float(compute="_compute_kpis", digits=(16, 2))
    current_stock_value = fields.Monetary(compute="_compute_kpis", currency_field="currency_id")
    pending_supplier_orders = fields.Integer(compute="_compute_kpis")
    awaiting_purchase_approval = fields.Integer(compute="_compute_kpis")
    pipeline_opportunities = fields.Integer(compute="_compute_kpis")
    pipeline_expected_value = fields.Monetary(compute="_compute_kpis", currency_field="currency_id")
    pipeline_weighted_value = fields.Monetary(compute="_compute_kpis", currency_field="currency_id")
    todays_absences = fields.Integer(compute="_compute_kpis")
    week_deliveries = fields.Integer(compute="_compute_kpis")
    material_cost = fields.Monetary(compute="_compute_kpis", currency_field="currency_id")
    access_notice = fields.Char(compute="_compute_kpis")

    _sql_constraints = [
        ("company_unique", "unique(company_id)", "Only one dashboard is allowed per company."),
    ]

    def _month_bounds(self):
        self.ensure_one()
        start = self.as_of_date.replace(day=1)
        next_month = (start.replace(day=28) + timedelta(days=4)).replace(day=1)
        return start, next_month - timedelta(days=1)

    def _week_bounds(self):
        self.ensure_one()
        start = self.as_of_date - timedelta(days=self.as_of_date.weekday())
        return start, start + timedelta(days=6)

    def _revenue_domain(self):
        start, end = self._month_bounds()
        return [
            ("company_id", "=", self.company_id.id), ("parent_state", "=", "posted"),
            ("date", ">=", start), ("date", "<=", end),
            ("account_id.account_type", "in", ("income", "income_other")),
        ]

    def _unpaid_domain(self):
        return [
            ("company_id", "=", self.company_id.id), ("parent_state", "=", "posted"),
            ("account_id.account_type", "=", "asset_receivable"),
            ("reconciled", "=", False), ("date_maturity", "<", self.as_of_date - timedelta(days=30)),
        ]

    def _sale_domains(self):
        base = [
            ("company_id", "=", self.company_id.id),
            ("date_order", "<", fields.Datetime.to_datetime(self.as_of_date + timedelta(days=1))),
        ]
        return base + [("state", "in", ("sent", "sale", "done"))], base + [("state", "in", ("sale", "done"))]

    def _stock_value_domain(self):
        return [
            ("company_id", "=", self.company_id.id),
            ("create_date", "<", fields.Datetime.to_datetime(self.as_of_date + timedelta(days=1))),
        ]

    def _pending_purchase_orders(self):
        orders = self.env["purchase.order"].search([
            ("company_id", "=", self.company_id.id), ("state", "in", ("purchase", "done")),
        ])
        return orders.filtered(lambda order: any(
            line.product_id.type == "product" and line.qty_received < line.product_qty
            for line in order.order_line
        ))

    @api.depends("company_id", "as_of_date")
    @api.depends_context("uid", "company")
    def _compute_kpis(self):
        for dashboard in self:
            dashboard.update({field: 0 for field in dashboard._kpi_field_names()})
            dashboard.access_notice = False
            if not dashboard.company_id or not dashboard.as_of_date:
                continue
            unavailable = []

            def can_read(model, label):
                allowed = self.env[model].check_access_rights("read", raise_exception=False)
                if not allowed:
                    unavailable.append(label)
                return allowed

            move_lines = self.env["account.move.line"]
            revenue, unpaid = [], []
            if can_read("account.move.line", _("Accounting")):
                revenue = move_lines.read_group(dashboard._revenue_domain(), ["balance:sum"], [])
                unpaid = move_lines.read_group(dashboard._unpaid_domain(), ["amount_residual:sum"], [])
            eligible_domain, confirmed_domain = dashboard._sale_domains()
            eligible = confirmed = 0
            if can_read("sale.order", _("Sales")):
                eligible = self.env["sale.order"].search_count(eligible_domain)
                confirmed = self.env["sale.order"].search_count(confirmed_domain)
            stock_layers = []
            if can_read("stock.valuation.layer", _("Stock valuation")):
                stock_layers = self.env["stock.valuation.layer"].read_group(
                    dashboard._stock_value_domain(), ["value:sum"], []
                )
            opportunities = self.env["crm.lead"]
            if can_read("crm.lead", _("CRM")):
                opportunities = opportunities.search([
                    ("company_id", "=", dashboard.company_id.id), ("type", "=", "opportunity"),
                    ("active", "=", True), ("probability", "<", 100),
                ])
            leave_count = 0
            if "hr.leave" in self.env.registry.models:
                leaves = self.env["hr.leave"]
                if hasattr(leaves, "_elmokrif_count_approved_absences"):
                    leave_count = leaves._elmokrif_count_approved_absences(
                        dashboard.company_id, dashboard.as_of_date
                    )
                elif can_read("hr.leave", _("Absences")):
                    leave_count = len(set(leaves.search([
                        ("company_id", "=", dashboard.company_id.id), ("state", "=", "validate"),
                        ("request_date_from", "<=", dashboard.as_of_date),
                        ("request_date_to", ">=", dashboard.as_of_date),
                    ]).mapped("employee_id").ids))
            week_start, week_end = dashboard._week_bounds()
            deliveries = self.env["stock.picking"].search_count([
                ("company_id", "=", dashboard.company_id.id), ("picking_type_code", "=", "outgoing"),
                ("state", "in", ("confirmed", "waiting", "assigned", "partially_available")),
                ("scheduled_date", ">=", fields.Datetime.to_datetime(week_start)),
                ("scheduled_date", "<", fields.Datetime.to_datetime(week_end + timedelta(days=1))),
            ]) if can_read("stock.picking", _("Deliveries")) else 0
            pending_orders = self.env["purchase.order"]
            awaiting = 0
            if can_read("purchase.order", _("Purchases")):
                pending_orders = dashboard._pending_purchase_orders()
                awaiting = self.env["purchase.order"].search_count([
                    ("company_id", "=", dashboard.company_id.id), ("state", "=", "to approve"),
                ])
            if (
                can_read("project.project", _("Chantiers"))
                and can_read("stock.move", _("Material costs"))
                and self.env["stock.valuation.layer"].check_access_rights("read", raise_exception=False)
            ):
                chantiers = self.env["project.project"].search([
                    ("company_id", "=", dashboard.company_id.id), ("is_chantier", "=", True),
                ])
                dashboard.material_cost = sum(chantiers.mapped("material_cost"))
            dashboard.monthly_revenue = -(revenue[0].get("balance", 0.0) if revenue else 0.0)
            dashboard.unpaid_over_30 = abs(unpaid[0].get("amount_residual", 0.0) if unpaid else 0.0)
            dashboard.quotation_conversion = (confirmed * 100.0 / eligible) if eligible else 0.0
            dashboard.current_stock_value = stock_layers[0].get("value", 0.0) if stock_layers else 0.0
            dashboard.pending_supplier_orders = len(pending_orders)
            dashboard.awaiting_purchase_approval = awaiting
            dashboard.pipeline_opportunities = len(opportunities)
            dashboard.pipeline_expected_value = sum(opportunities.mapped("expected_revenue"))
            dashboard.pipeline_weighted_value = sum(
                item.expected_revenue * item.probability / 100.0 for item in opportunities
            )
            dashboard.todays_absences = leave_count
            dashboard.week_deliveries = deliveries
            if unavailable:
                dashboard.access_notice = _(
                    "Unavailable with your current access: %s. These indicators display zero."
                ) % ", ".join(unavailable)

    @api.model
    def _kpi_field_names(self):
        return (
            "monthly_revenue", "unpaid_over_30", "quotation_conversion", "current_stock_value",
            "pending_supplier_orders", "awaiting_purchase_approval", "pipeline_opportunities",
            "pipeline_expected_value", "pipeline_weighted_value", "todays_absences", "week_deliveries",
            "material_cost",
        )

    def _action(self, model, domain, name):
        self.ensure_one()
        return {"type": "ir.actions.act_window", "name": name, "res_model": model,
                "view_mode": "tree,form", "domain": domain}

    def action_open_revenue(self):
        return self._action("account.move.line", self._revenue_domain(), _("Monthly Revenue"))

    def action_open_unpaid(self):
        return self._action("account.move.line", self._unpaid_domain(), _("Invoices Unpaid Over 30 Days"))

    def action_open_opportunities(self):
        return self._action("crm.lead", [
            ("company_id", "=", self.company_id.id), ("type", "=", "opportunity"),
            ("active", "=", True), ("probability", "<", 100),
        ], _("Pipeline Opportunities"))

    def action_open_pending_purchase_orders(self):
        return self._action("purchase.order", [("id", "in", self._pending_purchase_orders().ids)], _("Pending Supplier Orders"))

    def action_open_deliveries(self):
        week_start, week_end = self._week_bounds()
        return self._action("stock.picking", [
            ("company_id", "=", self.company_id.id), ("picking_type_code", "=", "outgoing"),
            ("state", "in", ("confirmed", "waiting", "assigned", "partially_available")),
            ("scheduled_date", ">=", fields.Datetime.to_datetime(week_start)),
            ("scheduled_date", "<", fields.Datetime.to_datetime(week_end + timedelta(days=1))),
        ], _("This Week's Deliveries"))
