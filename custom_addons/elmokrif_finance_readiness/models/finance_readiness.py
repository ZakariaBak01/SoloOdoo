from markupsafe import Markup, escape

_FINANCE_WORKFLOW_TOKEN = object()

from odoo import _, api, fields, models
from odoo.exceptions import AccessError, UserError


class ChantierFinanceReadiness(models.Model):
    _name = "chantier.finance.readiness"
    _description = "Chantier Finance Readiness"
    _inherit = ["mail.thread", "mail.activity.mixin"]
    _order = "company_id"
    _check_company_auto = True

    company_id = fields.Many2one(
        "res.company",
        required=True,
        default=lambda self: self.env.company,
        ondelete="cascade",
        check_company=True,
        tracking=True,
    )
    name = fields.Char(related="company_id.name", store=True, readonly=True)
    state = fields.Selection(
        [("draft", "Not Approved"), ("approved", "Accountant Approved")],
        default="draft",
        required=True,
        readonly=True,
        copy=False,
        tracking=True,
    )
    legal_identity_reviewed = fields.Boolean(
        string="Company identity, address, ICE and RC reviewed", tracking=True
    )
    chart_accounts_reviewed = fields.Boolean(
        string="Chart, receivable/payable and income/expense accounts reviewed", tracking=True
    )
    taxes_reviewed = fields.Boolean(
        string="Taxes and fiscal positions approved for current obligations", tracking=True
    )
    journals_payments_reviewed = fields.Boolean(
        string="Sales, Purchase, Bank, Cash and payment methods reviewed", tracking=True
    )
    inventory_valuation_reviewed = fields.Boolean(
        string="Cost methods, automated valuation and stock accounts reviewed", tracking=True
    )
    analytic_policy_reviewed = fields.Boolean(
        string="Chantier analytic allocation and material-cost policy reviewed", tracking=True
    )
    reports_reconciliation_reviewed = fields.Boolean(
        string="Ledger, trial balance, aging and reconciliation reports demonstrated", tracking=True
    )
    lock_access_reviewed = fields.Boolean(
        string="Lock dates, posting rights and correction process reviewed", tracking=True
    )
    pilot_documents_reviewed = fields.Boolean(
        string="Invoice, bill, credit note, partial payment and bank matching pilot passed", tracking=True
    )
    review_notes = fields.Text(
        help="Record the accountant's evidence references, decisions and remaining limitations.",
        tracking=True,
    )
    approved_by_id = fields.Many2one(
        "res.users", readonly=True, copy=False, tracking=True
    )
    approved_at = fields.Datetime(readonly=True, copy=False, tracking=True)
    technical_ready = fields.Boolean(compute="_compute_technical_status")
    technical_status = fields.Html(
        compute="_compute_technical_status", sanitize=False
    )

    _sql_constraints = [
        (
            "company_unique",
            "unique(company_id)",
            "Only one finance readiness record is allowed per company.",
        ),
    ]

    @api.model
    def _checklist_fields(self):
        return (
            "legal_identity_reviewed",
            "chart_accounts_reviewed",
            "taxes_reviewed",
            "journals_payments_reviewed",
            "inventory_valuation_reviewed",
            "analytic_policy_reviewed",
            "reports_reconciliation_reviewed",
            "lock_access_reviewed",
            "pilot_documents_reviewed",
        )

    @api.model
    def _ensure_for_companies(self, companies=None):
        companies = companies or self.env["res.company"].sudo().search([])
        existing_company_ids = set(
            self.sudo().search([("company_id", "in", companies.ids)]).mapped(
                "company_id"
            ).ids
        )
        values = [
            {"company_id": company.id}
            for company in companies
            if company.id not in existing_company_ids
        ]
        return self.sudo().create(values) if values else self.browse()

    def _technical_checks(self):
        self.ensure_one()
        company = self.company_id
        env = self.sudo().env
        partner = company.partner_id
        modules = env["ir.module.module"].search([
            ("name", "in", ("account", "stock_account", "l10n_ma")),
            ("state", "=", "installed"),
        ])
        accounts = env["account.account"].search_count([
            ("company_id", "=", company.id),
            ("deprecated", "=", False),
        ])
        journals = env["account.journal"].search([
            ("company_id", "=", company.id),
            ("active", "=", True),
        ])
        journal_types = set(journals.mapped("type"))
        bank_cash = journals.filtered(lambda journal: journal.type in ("bank", "cash"))
        sales_taxes = env["account.tax"].search_count([
            ("company_id", "=", company.id),
            ("active", "=", True),
            ("type_tax_use", "=", "sale"),
        ])
        purchase_taxes = env["account.tax"].search_count([
            ("company_id", "=", company.id),
            ("active", "=", True),
            ("type_tax_use", "=", "purchase"),
        ])
        categories = env["product.category"].with_company(company).search([])
        automated_categories = categories.filtered(
            lambda category: category.property_valuation == "real_time"
        )
        configured_categories = automated_categories.filtered(
            lambda category: category.property_stock_journal
            and category.property_stock_account_input_categ_id
            and category.property_stock_account_output_categ_id
            and category.property_stock_valuation_account_id
        )
        analytic_accounts = env["account.analytic.account"].search_count([
            ("company_id", "in", (False, company.id)),
            ("chantier_id", "!=", False),
        ])
        legal_identity_ok = bool(
            company.name
            and company.name.strip().lower() != "my company"
            and partner.street
            and partner.city
            and len((partner.company_registry or "").strip()) == 15
            and (partner.company_registry or "").strip().isascii()
            and (partner.company_registry or "").strip().isdigit()
            and company.elmokrif_rc_number
        )
        return [
            (
                _("Company legal identity"),
                legal_identity_ok,
                _("Set the legal name, address, 15-digit ICE and separate RC reference."),
            ),
            (
                _("Morocco and MAD"),
                partner.country_id.code == "MA" and company.currency_id.name == "MAD",
                _("Set the company country to Morocco and currency to MAD."),
            ),
            (
                _("Moroccan accounting localization"),
                len(modules) == 3 and company.chart_template == "ma",
                _("Install account, stock_account and l10n_ma and use the Moroccan chart template."),
            ),
            (
                _("Active chart of accounts"),
                accounts > 0,
                _("Load and review the company's chart of accounts."),
            ),
            (
                _("Sales and purchase taxes"),
                sales_taxes > 0 and purchase_taxes > 0,
                _("Configure at least one active sales tax and one active purchase tax."),
            ),
            (
                _("Sales, Purchase, Bank and Cash journals"),
                {"sale", "purchase", "bank", "cash"}.issubset(journal_types),
                _("Create and review all four required journal types."),
            ),
            (
                _("Bank and cash payment methods"),
                bool(bank_cash) and all(
                    journal.inbound_payment_method_line_ids and journal.outbound_payment_method_line_ids
                    for journal in bank_cash
                ),
                _("Configure inbound and outbound payment methods on bank/cash journals."),
            ),
            (
                _("Automated inventory valuation"),
                bool(automated_categories and len(configured_categories) == len(automated_categories)),
                _("Configure at least one automated category with stock journal, input, output and valuation accounts."),
            ),
            (
                _("Chantier analytic source"),
                analytic_accounts > 0,
                _("Initialize a chantier and verify its analytic account."),
            ),
        ]

    def _get_technical_errors(self):
        self.ensure_one()
        return [detail for _label, passed, detail in self._technical_checks() if not passed]

    @api.depends("company_id", "company_id.name", "company_id.currency_id")
    def _compute_technical_status(self):
        for readiness in self:
            if not readiness.company_id:
                readiness.technical_ready = False
                readiness.technical_status = ""
                continue
            checks = readiness._technical_checks()
            readiness.technical_ready = all(passed for _label, passed, _detail in checks)
            rows = []
            for label, passed, detail in checks:
                icon = "fa-check-circle text-success" if passed else "fa-times-circle text-danger"
                explanation = _("Passed") if passed else detail
                rows.append(Markup(
                    '<li class="mb-1"><i class="fa {} me-2"></i><strong>{}</strong>: {}</li>'
                ).format(escape(icon), escape(label), escape(explanation)))
            readiness.technical_status = Markup("<ul class=\"list-unstyled\">{}</ul>").format(
                Markup().join(rows)
            )

    @api.model_create_multi
    def create(self, vals_list):
        if not self.env.su and not self.env.user.has_group("account.group_account_manager"):
            raise AccessError(_("Only an Accounting Administrator can create finance readiness records."))
        evidence = {"state", "approved_by_id", "approved_at"}
        default_fields = {key[8:] for key in self.env.context if key.startswith("default_")}
        in_workflow = self.env.context.get("_finance_workflow_token") is _FINANCE_WORKFLOW_TOKEN
        if not in_workflow and (evidence.intersection(default_fields) or any(evidence.intersection(values) for values in vals_list)):
            raise UserError(_("Finance approval evidence is managed by the finance-readiness workflow."))
        return super().create(vals_list)

    def write(self, vals):
        protected = set(self._checklist_fields()) | {"review_notes", "company_id"}
        if protected.intersection(vals) and not self.env.su:
            if not self.env.user.has_group("account.group_account_manager"):
                raise AccessError(_("Only an Accounting Administrator can edit finance readiness."))
        if "company_id" in vals and any(record.company_id.id != vals["company_id"] for record in self):
            raise UserError(_("The company cannot be changed on a finance readiness record."))
        in_workflow = self.env.context.get("_finance_workflow_token") is _FINANCE_WORKFLOW_TOKEN
        if {"state", "approved_by_id", "approved_at"}.intersection(vals) and not in_workflow:
            raise UserError(_("Use the approval or reset action to change finance readiness."))
        if protected.intersection(vals) and any(record.state == "approved" for record in self):
            vals = dict(vals, state="draft", approved_by_id=False, approved_at=False)
        return super().write(vals)

    def _workflow_write(self, vals):
        return self.with_context(_finance_workflow_token=_FINANCE_WORKFLOW_TOKEN).write(vals)

    def unlink(self):
        raise UserError(_("Finance readiness history cannot be deleted."))

    def action_approve(self):
        if not self.env.user.has_group("account.group_account_manager"):
            raise AccessError(_("Only an Accounting Administrator can approve finance readiness."))
        for readiness in self:
            self.env.cr.execute(
                "SELECT id FROM chantier_finance_readiness WHERE id = %s FOR UPDATE",
                [readiness.id],
            )
            readiness.invalidate_recordset()
            missing = [
                readiness._fields[field_name].string
                for field_name in readiness._checklist_fields()
                if not readiness[field_name]
            ]
            if missing:
                raise UserError(_("Complete every accountant checklist item: %s") % ", ".join(missing))
            if not (readiness.review_notes or "").strip():
                raise UserError(_("Record the accountant's evidence and decisions before approval."))
            errors = readiness._get_technical_errors()
            if errors:
                raise UserError(_("Technical finance checks are not ready:\n- %s") % "\n- ".join(errors))
            readiness._workflow_write({
                "state": "approved",
                "approved_by_id": self.env.user.id,
                "approved_at": fields.Datetime.now(),
            })
            readiness.sudo().message_post(
                body=_("Finance readiness approved by %s.") % self.env.user.display_name,
                author_id=self.env.ref("base.partner_root").id,
            )
        return True

    def action_reset(self):
        if not self.env.user.has_group("account.group_account_manager"):
            raise AccessError(_("Only an Accounting Administrator can reset finance readiness."))
        self._workflow_write({
            "state": "draft",
            "approved_by_id": False,
            "approved_at": False,
        })
        return True
