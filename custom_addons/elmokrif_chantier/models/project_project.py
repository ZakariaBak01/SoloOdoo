from odoo import _, api, fields, models
from odoo.exceptions import AccessError, UserError, ValidationError


WORK_TYPE_SELECTION = [
    ("construction", "Construction"),
    ("carpentry", "Carpentry"),
    ("finishing", "Finishing"),
]

CHANTIER_STATE_SELECTION = [
    ("draft", "Draft"),
    ("approved", "Approved"),
    ("in_progress", "In Progress"),
    ("on_hold", "On Hold"),
    ("completed", "Completed"),
    ("closed", "Closed"),
]


class ProjectProject(models.Model):
    _inherit = "project.project"
    _check_company_auto = True

    is_chantier = fields.Boolean(string="Is a Chantier", tracking=True, index=True)
    chantier_reference = fields.Char(
        string="Chantier Reference",
        copy=False,
        readonly=True,
        tracking=True,
        index=True,
    )
    chantier_state = fields.Selection(
        CHANTIER_STATE_SELECTION,
        string="Chantier Status",
        default="draft",
        required=True,
        copy=False,
        tracking=True,
        index=True,
    )
    chantier_region = fields.Char(string="Region", tracking=True)
    work_type = fields.Selection(
        WORK_TYPE_SELECTION,
        string="Primary Work Type",
        tracking=True,
    )
    site_partner_id = fields.Many2one(
        "res.partner",
        string="Site Address",
        tracking=True,
        check_company=True,
        domain="['|', ('company_id', '=', False), ('company_id', '=', company_id)]",
    )
    warehouse_id = fields.Many2one(
        "stock.warehouse",
        string="Supplying Warehouse",
        tracking=True,
        check_company=True,
        domain="[('company_id', '=', company_id)]",
    )
    site_location_id = fields.Many2one(
        "stock.location",
        string="Site Stock Location",
        copy=False,
        readonly=True,
        tracking=True,
        check_company=True,
        domain="[('usage', '=', 'internal'), ('company_id', '=', company_id)]",
    )
    reopen_reason = fields.Text(
        string="Reopening Reason",
        copy=False,
        groups="elmokrif_chantier.group_chantier_manager",
    )
    chantier_initialized = fields.Boolean(
        string="Chantier Initialized",
        compute="_compute_chantier_initialized",
    )

    _sql_constraints = [
        (
            "chantier_reference_company_uniq",
            "unique(chantier_reference, company_id)",
            "The chantier reference must be unique per company.",
        ),
        (
            "chantier_site_location_uniq",
            "unique(site_location_id)",
            "A site stock location can belong to only one chantier.",
        ),
    ]

    @api.depends("analytic_account_id", "site_location_id")
    def _compute_chantier_initialized(self):
        for project in self:
            project.chantier_initialized = bool(
                project.analytic_account_id and project.site_location_id
            )

    @api.model_create_multi
    def create(self, vals_list):
        for vals in vals_list:
            is_chantier = vals.get(
                "is_chantier", self.env.context.get("default_is_chantier", False)
            )
            # Odoo's Project quick-create dialog only sends the project name.
            # A chantier must be attached to the currently active company.
            if is_chantier and not vals.get("company_id"):
                vals["company_id"] = self.env.company.id

            if is_chantier and not vals.get("chantier_reference"):
                company = self.env["res.company"].browse(
                    vals.get("company_id")
                ) or self.env.company
                vals["chantier_reference"] = (
                    self.env["ir.sequence"]
                    .with_company(company)
                    .next_by_code("elmokrif.chantier")
                )
        return super().create(vals_list)

    def write(self, vals):
        if "chantier_reference" in vals and any(
            project.chantier_reference
            and project.chantier_reference != vals["chantier_reference"]
            for project in self
        ):
            raise UserError(_("A chantier reference cannot be changed."))
        if "site_location_id" in vals and any(
            project.site_location_id.id != vals["site_location_id"] for project in self
        ):
            raise UserError(
                _("Use Initialize Chantier to assign the site stock location.")
            )
        if vals.get("is_chantier") is False and any(
            project.site_location_id or project.chantier_state != "draft"
            for project in self
        ):
            raise UserError(
                _("An initialized or active chantier cannot be converted to an ordinary project.")
            )
        if "warehouse_id" in vals and any(
            project.chantier_initialized
            and project.warehouse_id.id != vals["warehouse_id"]
            for project in self
        ):
            raise UserError(
                _("The supplying warehouse cannot be changed after initialization.")
            )
        if "chantier_state" in vals:
            self._validate_chantier_state_change(vals["chantier_state"], vals)

        result = super().write(vals)

        for project in self.filtered(lambda item: item.is_chantier and not item.chantier_reference):
            reference = (
                self.env["ir.sequence"]
                .with_company(project.company_id or self.env.company)
                .next_by_code("elmokrif.chantier")
            )
            super(ProjectProject, project).write({"chantier_reference": reference})

        return result

    def _validate_chantier_state_change(self, target_state, vals):
        allowed_transitions = {
            "draft": {"approved"},
            "approved": {"in_progress"},
            "in_progress": {"on_hold", "completed"},
            "on_hold": {"in_progress", "completed"},
            "completed": {"closed", "in_progress"},
            "closed": {"approved"},
        }
        manager_states = {"approved", "closed"}

        if not (
            self.env.su
            or self.env.user.has_group("elmokrif_chantier.group_chantier_user")
        ):
            raise AccessError(_("Only a chantier user can change the chantier status."))

        for project in self:
            if project.chantier_state == target_state:
                continue
            if not project.is_chantier:
                raise ValidationError(_("Only a chantier can use the chantier lifecycle."))
            if target_state not in allowed_transitions.get(project.chantier_state, set()):
                raise UserError(
                    _(
                        "The chantier cannot move from %(current)s to %(target)s."
                    )
                    % {
                        "current": project.chantier_state,
                        "target": target_state,
                    }
                )
            if target_state in manager_states and not (
                self.env.su
                or self.env.user.has_group(
                    "elmokrif_chantier.group_chantier_manager"
                )
            ):
                raise AccessError(_("Only a chantier manager can approve or close a chantier."))
            if project.chantier_state == "closed" and not (
                vals.get("reopen_reason") or project.reopen_reason
            ):
                raise ValidationError(_("A reopening reason is required."))

    @api.constrains(
        "is_chantier",
        "company_id",
        "warehouse_id",
        "site_location_id",
        "analytic_account_id",
    )
    def _check_chantier_company_consistency(self):
        for project in self.filtered("is_chantier"):
            if not project.company_id:
                raise ValidationError(_("A chantier must belong to a company."))
            linked_records = (
                project.warehouse_id.company_id
                | project.site_location_id.company_id
                | project.analytic_account_id.company_id
            )
            if any(company != project.company_id for company in linked_records):
                raise ValidationError(
                    _("The chantier, warehouse, analytic account and site location must use the same company.")
                )
            if project.site_location_id and project.site_location_id.usage != "internal":
                raise ValidationError(_("A chantier stock location must be internal."))

    def action_initialize_chantier(self):
        self._ensure_chantier_manager()
        for project in self.sorted("id"):
            if not project.is_chantier:
                raise UserError(_("Mark the project as a chantier before initializing it."))
            if not project.company_id:
                raise UserError(_("Set the chantier company before initializing it."))

            self.env.cr.execute(
                "SELECT id FROM project_project WHERE id = %s FOR UPDATE",
                [project.id],
            )
            project.invalidate_recordset(
                ["analytic_account_id", "warehouse_id", "site_location_id"]
            )

            created_items = []
            if not project.analytic_account_id:
                project._create_analytic_account()
                created_items.append(_("analytic account"))

            warehouse = project.warehouse_id or self.env["stock.warehouse"].search(
                [("company_id", "=", project.company_id.id)], limit=1
            )
            if not warehouse:
                raise UserError(
                    _("Create a warehouse for %(company)s before initializing the chantier.", company=project.company_id.display_name)
                )
            if not project.warehouse_id:
                project.warehouse_id = warehouse

            location = project.site_location_id or self.env["stock.location"].with_context(
                active_test=False
            ).search([("chantier_id", "=", project.id)], limit=1)
            if not location:
                location = self.env["stock.location"].create(
                    {
                        "name": project.chantier_reference or project.name,
                        "location_id": warehouse.lot_stock_id.id,
                        "usage": "internal",
                        "company_id": project.company_id.id,
                        "chantier_id": project.id,
                    }
                )
                created_items.append(_("site stock location"))
            if project.site_location_id != location:
                super(ProjectProject, project).write({"site_location_id": location.id})

            if created_items:
                project.message_post(
                    body=_("Chantier initialized. Created: %s", ", ".join(created_items))
                )

        return True

    def _ensure_chantier_manager(self):
        if not (
            self.env.su
            or self.env.user.has_group("elmokrif_chantier.group_chantier_manager")
        ):
            raise AccessError(_("Only a chantier manager can perform this action."))

    def _get_chantier_closure_blockers(self):
        self.ensure_one()
        blockers = []
        open_task_count = self.env["project.task"].search_count(
            [
                ("project_id", "=", self.id),
                ("state", "in", list(self.env["project.task"].OPEN_STATES)),
            ]
        )
        if open_task_count:
            blockers.append(_("%(count)s open task(s)", count=open_task_count))
        if self.site_location_id:
            remaining_quant_count = self.env["stock.quant"].search_count(
                [
                    ("location_id", "child_of", self.site_location_id.id),
                    ("quantity", "!=", 0),
                ]
            )
            if remaining_quant_count:
                blockers.append(_("remaining site stock"))
        return blockers

    def _set_chantier_state(self, state):
        self.write({"chantier_state": state})
        return True

    def action_approve_chantier(self):
        self._ensure_chantier_manager()
        for project in self:
            if not project.chantier_initialized:
                raise UserError(_("Initialize the chantier before approving it."))
        return self._set_chantier_state("approved")

    def action_start_chantier(self):
        self._ensure_chantier_user()
        return self._set_chantier_state("in_progress")

    def action_hold_chantier(self):
        self._ensure_chantier_user()
        return self._set_chantier_state("on_hold")

    def action_complete_chantier(self):
        self._ensure_chantier_user()
        return self._set_chantier_state("completed")

    def action_close_chantier(self):
        self._ensure_chantier_manager()
        for project in self:
            blockers = project._get_chantier_closure_blockers()
            if blockers:
                raise UserError(
                    _(
                        "Resolve these items before closing %(chantier)s:\n- %(items)s",
                        chantier=project.display_name,
                        items="\n- ".join(blockers),
                    )
                )
        return self._set_chantier_state("closed")

    def action_reopen_chantier(self):
        self._ensure_chantier_manager()
        return self._set_chantier_state("approved")

    def _ensure_chantier_accepts_commitments(self):
        for project in self:
            if not project.is_chantier or project.chantier_state != "in_progress":
                raise UserError(
                    _("New commitments require a chantier that is in progress.")
                )

    def _ensure_chantier_user(self):
        if not (
            self.env.su
            or self.env.user.has_group("elmokrif_chantier.group_chantier_user")
        ):
            raise AccessError(_("Only a chantier user can perform this action."))
