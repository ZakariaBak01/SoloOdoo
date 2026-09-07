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
        tracking=True,
        groups="elmokrif_chantier.group_chantier_manager",
    )
    chantier_analytic_plan_id = fields.Many2one(
        "account.analytic.plan",
        string="Analytic Plan",
        related="analytic_account_id.plan_id",
        readonly=True,
    )
    chantier_initialized = fields.Boolean(
        string="Chantier Initialized",
        compute="_compute_chantier_initialized",
    )
    can_manage_chantier = fields.Boolean(
        string="Can Manage Chantier",
        compute="_compute_can_manage_chantier",
        # Odoo evaluates form modifiers before non-stored computed fields are
        # calculated for a new record.  Supplying the same value through
        # default_get keeps draft master-data fields editable for managers.
        default=lambda self: self.env.su or self.env.user.has_group(
            "elmokrif_chantier.group_chantier_manager"
        ),
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

    @api.depends(
        "analytic_account_id.plan_id",
        "analytic_account_id.chantier_id",
        "site_location_id.chantier_id",
    )
    def _compute_chantier_initialized(self):
        chantier_plan = self.env.ref(
            "elmokrif_chantier.analytic_plan_chantier",
            raise_if_not_found=False,
        )
        for project in self:
            project.chantier_initialized = bool(
                chantier_plan
                and project.analytic_account_id.plan_id == chantier_plan
                and project.analytic_account_id.chantier_id == project
                and project.site_location_id.chantier_id == project
            )

    @api.depends_context("uid")
    def _compute_can_manage_chantier(self):
        can_manage = self.env.su or self.env.user.has_group(
            "elmokrif_chantier.group_chantier_manager"
        )
        for project in self:
            project.can_manage_chantier = can_manage

    @api.model
    def default_get(self, fields_list):
        defaults = super().default_get(fields_list)
        # The supplying-warehouse domain is scoped to company_id.  Project's
        # standard defaults do not provide a company for a new record, so a
        # chantier opened from its action would otherwise see no warehouse.
        if (
            self.env.context.get("default_is_chantier")
            and "company_id" in fields_list
            and not defaults.get("company_id")
        ):
            defaults["company_id"] = self.env.company.id
        return defaults

    @api.model_create_multi
    def create(self, vals_list):
        form_analytic_account_ids = []
        for vals in vals_list:
            is_chantier = vals.get(
                "is_chantier", self.env.context.get("default_is_chantier", False)
            )
            if is_chantier and not (
                self.env.su
                or self.env.user.has_group(
                    "elmokrif_chantier.group_chantier_manager"
                )
            ):
                raise AccessError(_("Only a chantier manager can create a chantier."))
            if is_chantier and vals.get("chantier_state", "draft") != "draft":
                raise UserError(_("A new chantier must start in Draft."))
            if is_chantier and vals.get("chantier_reference"):
                raise UserError(_("The chantier reference is generated automatically."))
            form_create = (
                is_chantier
                and self.env.context.get("default_is_chantier")
                and not self.env.context.get("chantier_initialization")
            )
            analytic_account_id = vals.get("analytic_account_id")
            if is_chantier and vals.get("site_location_id"):
                if form_create:
                    vals.pop("site_location_id")
                else:
                    raise UserError(
                        _("Create chantier analytic and stock resources with Initialize Chantier.")
                    )
            if is_chantier and analytic_account_id and not form_create:
                raise UserError(
                    _("Create chantier analytic and stock resources with Initialize Chantier.")
                )
            # hr_timesheet creates an analytic account before calling this
            # method when Timesheets are enabled.  Preserve that mandatory
            # account for the New Chantier form, then make it chantier-owned
            # immediately after the project receives its database ID.
            form_analytic_account_ids.append(
                analytic_account_id if form_create else False
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
        create_context = {}
        if any(form_analytic_account_ids):
            create_context["chantier_form_create"] = True
        projects = super(ProjectProject, self.with_context(**create_context)).create(vals_list)
        for project, analytic_account_id in zip(projects, form_analytic_account_ids):
            if analytic_account_id:
                analytic_account = self.env["account.analytic.account"].browse(
                    analytic_account_id
                )
                analytic_account.sudo().with_context(
                    chantier_initialization=True
                ).write({
                    "company_id": project.company_id.id,
                    "plan_id": project._get_chantier_analytic_plan().id,
                    "chantier_id": project.id,
                })
                project._check_chantier_company_consistency()
        projects.filtered("is_chantier")._subscribe_chantier_assignees()
        return projects

    def write(self, vals):
        self._ensure_chantier_write_scope(vals)
        becoming_chantier = vals.get("is_chantier") is True
        if becoming_chantier and any(
            not project.is_chantier and project.chantier_state != "draft"
            for project in self
        ):
            raise UserError(_("A project can only become a chantier in Draft."))
        if becoming_chantier and vals.get("chantier_reference"):
            raise UserError(_("The chantier reference is generated automatically."))
        if "chantier_reference" in vals and any(
            project.chantier_reference
            and project.chantier_reference != vals["chantier_reference"]
            for project in self
        ):
            raise UserError(_("A chantier reference cannot be changed."))
        system_link_write = self.env.context.get("chantier_initialization")
        if not system_link_write and "site_location_id" in vals and any(
            (project.is_chantier or becoming_chantier)
            and project.site_location_id.id != vals["site_location_id"]
            for project in self
        ):
            raise UserError(
                _("Use Initialize Chantier to assign the site stock location.")
            )
        if not system_link_write and "analytic_account_id" in vals and any(
            (project.is_chantier or becoming_chantier)
            and project.analytic_account_id.id != vals["analytic_account_id"]
            for project in self
        ):
            raise UserError(
                _("Use Initialize Chantier to assign the analytic account.")
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
        if "active" in vals and any(project.is_chantier for project in self):
            self._ensure_chantier_manager()
            if not vals["active"] and any(
                project.chantier_state != "closed" for project in self.filtered("is_chantier")
            ):
                raise UserError(_("Only a closed chantier can be archived."))
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

        if {"is_chantier", "user_id", "favorite_user_ids"}.intersection(vals):
            self.filtered("is_chantier")._subscribe_chantier_assignees()

        if vals.get("chantier_state") == "approved":
            self.filtered(
                lambda project: project.is_chantier
                and not project.chantier_initialized
            )._initialize_chantier_resources()

        return result

    def _subscribe_chantier_assignees(self):
        """Keep standard private-project visibility aligned with site assignment."""
        for project in self:
            assigned_users = project.user_id | project.favorite_user_ids
            if assigned_users:
                project.sudo().message_subscribe(
                    partner_ids=assigned_users.partner_id.ids
                )

    def unlink(self):
        if any(project.is_chantier for project in self):
            raise UserError(
                _("Chantiers cannot be deleted. Close and archive them instead.")
            )
        return super().unlink()

    def _ensure_chantier_write_scope(self, vals):
        """Keep the write ACL granted to chantier users inside chantier scope."""
        if self.env.su:
            return
        is_chantier_user = self.env.user.has_group(
            "elmokrif_chantier.group_chantier_user"
        )
        is_chantier_manager = self.env.user.has_group(
            "elmokrif_chantier.group_chantier_manager"
        )
        is_project_manager = self.env.user.has_group(
            "project.group_project_manager"
        )
        chantier_records = self.filtered("is_chantier")
        if chantier_records and not is_chantier_user:
            raise AccessError(_("Only a chantier user can modify a chantier."))
        if "is_chantier" in vals and not is_chantier_manager:
            raise AccessError(
                _("Only a chantier manager can change the chantier classification.")
            )
        if is_chantier_user and not is_chantier_manager:
            ordinary_projects = self - chantier_records
            if ordinary_projects and not is_project_manager:
                raise AccessError(
                    _("Chantier users cannot modify ordinary projects.")
                )
            manager_fields = {
                "analytic_account_id",
                "chantier_region",
                "company_id",
                "date",
                "date_start",
                "favorite_user_ids",
                "name",
                "partner_id",
                "site_location_id",
                "site_partner_id",
                "user_id",
                "warehouse_id",
                "work_type",
            }
            if chantier_records and manager_fields.intersection(vals):
                raise AccessError(
                    _("Only a chantier manager can change chantier master data.")
                )

    def _validate_chantier_state_change(self, target_state, vals):
        allowed_transitions = {
            "draft": {"approved"},
            "approved": {"in_progress"},
            "in_progress": {"on_hold", "completed"},
            "on_hold": {"in_progress", "completed"},
            "completed": {"closed", "approved"},
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
            if target_state == "approved":
                if project.chantier_state == "draft":
                    project._ensure_chantier_master_data(vals)
                elif not vals.get("reopen_reason", project.reopen_reason):
                    raise ValidationError(_("A reopening reason is required."))
            if target_state == "in_progress" and project.chantier_state == "approved":
                if not project.chantier_initialized:
                    raise ValidationError(
                        _("Initialize the chantier before starting it.")
                    )
            if target_state == "closed":
                blockers = project._get_chantier_closure_blockers()
                if blockers:
                    raise UserError(
                        _("Resolve these items before closing %(chantier)s:\n- %(items)s")
                        % {
                            "chantier": project.display_name,
                            "items": "\n- ".join(blockers),
                        }
                    )

    def _ensure_chantier_master_data(self, vals=None):
        """Validate approval data for buttons as well as imports and RPC writes."""
        vals = vals or {}
        for project in self:
            missing_fields = []
            if not vals.get("chantier_region", project.chantier_region):
                missing_fields.append(_("Region"))
            if not vals.get("work_type", project.work_type):
                missing_fields.append(_("Primary Work Type"))
            if not vals.get("site_partner_id", project.site_partner_id.id):
                missing_fields.append(_("Site Address"))
            if not vals.get("warehouse_id", project.warehouse_id.id):
                missing_fields.append(_("Supplying Warehouse"))
            if not vals.get("partner_id", project.partner_id.id):
                missing_fields.append(_("Customer"))
            if not vals.get("user_id", project.user_id.id):
                missing_fields.append(_("Chantier Manager"))
            if not vals.get("date_start", project.date_start):
                missing_fields.append(_("Planned Start Date"))
            if not vals.get("date", project.date):
                missing_fields.append(_("Planned End Date"))
            if missing_fields:
                raise UserError(
                    _("Complete the following fields before approving the chantier:\n- %s")
                    % "\n- ".join(missing_fields)
                )

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
                    _(
                        "The chantier, warehouse, analytic account and site "
                        "location must use the same company."
                    )
                )
            if (
                project.site_location_id
                and project.site_location_id.usage != "internal"
            ):
                raise ValidationError(_("A chantier stock location must be internal."))
            if (
                project.site_location_id
                and project.site_location_id.chantier_id != project
            ):
                raise ValidationError(
                    _("The chantier and site stock location must link to each other.")
                )
            if project.analytic_account_id and not self.env.context.get(
                "chantier_form_create"
            ):
                chantier_plan = project._get_chantier_analytic_plan()
                if project.analytic_account_id.plan_id != chantier_plan:
                    raise ValidationError(
                        _("A chantier analytic account must use the Chantiers plan.")
                    )
                if project.analytic_account_id.chantier_id != project:
                    raise ValidationError(
                        _("The chantier and analytic account must link to each other.")
                    )
                other_chantier = (
                    self.with_context(active_test=False).sudo().search(
                        [
                            ("id", "!=", project.id),
                            ("is_chantier", "=", True),
                            (
                                "analytic_account_id",
                                "=",
                                project.analytic_account_id.id,
                            ),
                        ],
                        limit=1,
                    )
                )
                if other_chantier:
                    raise ValidationError(
                        _("An analytic account can belong to only one chantier.")
                    )

    def action_initialize_chantier(self):
        self._ensure_chantier_manager()
        return self._initialize_chantier_resources()

    def _get_chantier_analytic_plan(self):
        return self.env.ref("elmokrif_chantier.analytic_plan_chantier")

    def _create_chantier_analytic_account(self):
        self.ensure_one()
        return self.env["account.analytic.account"].sudo().with_context(
            chantier_initialization=True
        ).create(
            {
                "name": self.name,
                "company_id": self.company_id.id,
                "partner_id": self.partner_id.id,
                "plan_id": self._get_chantier_analytic_plan().id,
                "chantier_id": self.id,
            }
        )

    def _initialize_chantier_resources(self):
        """Create or recover the system resources owned by a chantier."""
        for project in self.sorted("id"):
            if not project.is_chantier:
                raise UserError(_("Mark the project as a chantier before initializing it."))
            if project.chantier_state == "draft":
                raise UserError(_("Approve the chantier before initializing it."))
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
            analytic_account = project.analytic_account_id
            if analytic_account and (
                analytic_account.plan_id != project._get_chantier_analytic_plan()
            ):
                raise UserError(
                    _("The existing analytic account is not in the Chantiers plan.")
                )
            if analytic_account and not analytic_account.company_id:
                # Older chantiers could use a shared-company analytic account.
                # Once it becomes chantier-owned, give it the chantier company
                # before establishing the reciprocal link.
                analytic_account.sudo().with_context(
                    chantier_initialization=True
                ).write({"company_id": project.company_id.id})
            elif (
                analytic_account
                and analytic_account.company_id != project.company_id
            ):
                raise UserError(
                    _("The existing analytic account belongs to another company.")
                )
            if (
                analytic_account.chantier_id
                and analytic_account.chantier_id != project
            ):
                raise UserError(
                    _("The existing analytic account belongs to another chantier.")
                )
            if analytic_account and not analytic_account.chantier_id:
                analytic_account.sudo().with_context(
                    chantier_initialization=True
                ).write({"chantier_id": project.id})
                created_items.append(_("analytic account link"))
            if not analytic_account:
                analytic_account = project._create_chantier_analytic_account()
                super(
                    ProjectProject,
                    project.with_context(chantier_initialization=True),
                ).write({"analytic_account_id": analytic_account.id})
                created_items.append(_("analytic account"))

            warehouse = project.warehouse_id or self.env["stock.warehouse"].search(
                [("company_id", "=", project.company_id.id)], limit=1
            )
            if not warehouse:
                raise UserError(
                    _(
                        "Create a warehouse for %(company)s before initializing "
                        "the chantier.",
                        company=project.company_id.display_name,
                    )
                )
            if not project.warehouse_id:
                super(ProjectProject, project).write({"warehouse_id": warehouse.id})

            location = project.site_location_id or (
                self.env["stock.location"]
                .sudo()
                .with_context(active_test=False)
                .search([("chantier_id", "=", project.id)], limit=1)
            )
            if not location:
                # A chantier manager should not need broad Inventory Administrator
                # rights merely to create this system-owned location.
                location = self.env["stock.location"].sudo().with_context(
                    chantier_initialization=True
                ).create(
                    {
                        "name": project.chantier_reference or project.name,
                        # Site locations must be siblings of warehouse Stock.  A child of
                        # Stock is included in its reservation domain and can therefore
                        # satisfy another chantier's warehouse delivery.
                        "location_id": warehouse.view_location_id.id,
                        "usage": "internal",
                        "company_id": project.company_id.id,
                        "chantier_id": project.id,
                    }
                )
                created_items.append(_("site stock location"))
            elif location.chantier_id and location.chantier_id != project:
                raise UserError(
                    _("The site stock location belongs to another chantier.")
                )
            elif not location.chantier_id:
                location.sudo().with_context(chantier_initialization=True).write(
                    {"chantier_id": project.id}
                )
                created_items.append(_("site stock location link"))
            if project.site_location_id != location:
                super(
                    ProjectProject,
                    project.with_context(chantier_initialization=True),
                ).write({"site_location_id": location.id})

            if created_items:
                project.message_post(
                    body=_("Chantier initialized. Created: %s", ", ".join(created_items))
                )

        return True

    def _relocate_legacy_site_locations(self):
        """Move old site locations out of warehouse Stock and repair reservations.

        This is deliberately private: it is used by the module upgrade script,
        where it runs as administrator and preserves each affected transfer's
        demand by unreserving and reassigning it.
        """
        location_model = self.env["stock.location"].with_context(active_test=False)
        move_model = self.env["stock.move"]
        for project in self.filtered(
            lambda item: item.site_location_id and item.warehouse_id
        ):
            location = project.site_location_id.with_context(active_test=False)
            warehouse = project.warehouse_id
            stock_location = warehouse.lot_stock_id
            warehouse_root = warehouse.view_location_id
            if not warehouse_root or location == stock_location:
                continue
            if location not in location_model.search([
                ("id", "child_of", stock_location.id),
            ]):
                continue

            affected_moves = move_model.search([
                ("location_id", "=", stock_location.id),
                ("state", "in", ("assigned", "partially_available")),
                ("move_line_ids.location_id", "child_of", location.id),
            ])
            affected_moves._do_unreserve()
            location.write({"location_id": warehouse_root.id})
            affected_moves._action_assign()

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
        self._ensure_chantier_master_data()
        return self._set_chantier_state("approved")

    def action_start_chantier(self):
        self._ensure_chantier_user()
        self.filtered(
            lambda project: project.chantier_state == "approved"
            and not project.chantier_initialized
        )._initialize_chantier_resources()
        return self._set_chantier_state("in_progress")

    def action_hold_chantier(self):
        self._ensure_chantier_user()
        return self._set_chantier_state("on_hold")

    def action_complete_chantier(self):
        self._ensure_chantier_user()
        return self._set_chantier_state("completed")

    def action_close_chantier(self):
        self._ensure_chantier_manager()
        return self._set_chantier_state("closed")

    def action_reopen_chantier(self):
        self._ensure_chantier_manager()
        for project in self:
            if not project.reopen_reason:
                raise ValidationError(_("A reopening reason is required."))
            reason = project.reopen_reason
            project.write({
                "chantier_state": "approved",
                "reopen_reason": reason,
            })
            project.message_post(
                body=_("Chantier reopened. Reason: %s", reason)
            )
            super(ProjectProject, project).write({"reopen_reason": False})
        return True

    def action_archive_chantier(self):
        self._ensure_chantier_manager()
        for project in self:
            if not project.is_chantier or project.chantier_state != "closed":
                raise UserError(_("Only a closed chantier can be archived."))
        self.write({"active": False})
        return True

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
