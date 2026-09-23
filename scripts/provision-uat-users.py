"""Provision the named UI/UX UAT personas in an Odoo shell.

Run by piping this file into ``odoo shell -d <database> --no-http``.
All accounts use one shared password for local UAT. Set UAT_SHARED_PASSWORD to
override the default test password.
"""

import os


COMPANY_A_NAME = "EL MOKRIF COMPANY SARL"
COMPANY_B_NAME = "UAT ISOLATION COMPANY B"
SHARED_PASSWORD = os.environ.get("UAT_SHARED_PASSWORD", "UAT2026!")
if not SHARED_PASSWORD:
    raise RuntimeError("UAT_SHARED_PASSWORD cannot be empty.")


def ref(xmlid):
    record = env.ref(xmlid, raise_if_not_found=False)
    if not record:
        raise RuntimeError(f"Required access group is unavailable: {xmlid}")
    return record


morocco = env["res.country"].search([("code", "=", "MA")], limit=1)
mad = env["res.currency"].search([("name", "=", "MAD")], limit=1)
if not morocco or not mad:
    raise RuntimeError("Morocco or MAD master data is unavailable.")

company_a = env["res.company"].search([("name", "=", COMPANY_A_NAME)], limit=1)
if not company_a:
    company_a = env["res.company"].search(
        [("name", "in", ["EL MOKRIF COMPANY", "EL MOKRIF COMPANY SARL"])],
        limit=1,
    )
if not company_a:
    # A fresh Odoo database contains one required default company. Reuse it so
    # the UAT database contains exactly the two companies in the playbook.
    company_a = env.company
if company_a:
    company_a.write(
        {
            "name": COMPANY_A_NAME,
            "country_id": morocco.id,
            "currency_id": mad.id,
            "email": "uat.company.a@example.test",
        }
    )
else:
    company_a = env["res.company"].create(
        {
            "name": COMPANY_A_NAME,
            "country_id": morocco.id,
            "currency_id": mad.id,
            "email": "uat.company.a@example.test",
        }
    )

company_b = env["res.company"].search([("name", "=", COMPANY_B_NAME)], limit=1)
if company_b:
    company_b.write({
        "country_id": morocco.id,
        "currency_id": mad.id,
        "email": "uat.company.b@example.test",
    })
else:
    company_b = env["res.company"].create(
        {
            "name": COMPANY_B_NAME,
            "country_id": morocco.id,
            "currency_id": mad.id,
            "email": "uat.company.b@example.test",
        }
    )


def upsert_partner(name, values):
    partner = env["res.partner"].with_context(active_test=False).search(
        [("name", "=", name), ("company_id", "in", [False, company_a.id])],
        limit=1,
    )
    values = {"name": name, "active": True, **values}
    if partner:
        partner.write(values)
    else:
        partner = env["res.partner"].create(values)
    return partner


uat_customer_a = upsert_partner(
    "UAT Customer A",
    {
        "customer_rank": 1,
        "company_id": company_a.id,
        "country_id": morocco.id,
    },
)
uat_customer_site = upsert_partner(
    "UAT Customer A Site",
    {
        "parent_id": uat_customer_a.id,
        "type": "delivery",
        "company_id": company_a.id,
        "country_id": morocco.id,
        "street": "UAT Construction Site",
        "city": "Casablanca",
    },
)
uat_supplier_a = upsert_partner(
    "UAT Supplier A",
    {
        "supplier_rank": 1,
        "company_id": company_a.id,
        "country_id": morocco.id,
    },
)
uat_supplier_b = upsert_partner(
    "UAT Supplier B",
    {
        "supplier_rank": 1,
        "company_id": company_a.id,
        "country_id": morocco.id,
    },
)

company_b_customer = env["res.partner"].with_context(active_test=False).search(
    [("name", "=", "UAT Company B Customer"), ("company_id", "=", company_b.id)],
    limit=1,
)
company_b_customer_values = {
    "name": "UAT Company B Customer",
    "customer_rank": 1,
    "company_id": company_b.id,
    "country_id": morocco.id,
    "active": True,
}
if company_b_customer:
    company_b_customer.write(company_b_customer_values)
else:
    company_b_customer = env["res.partner"].create(company_b_customer_values)

# Keep the disposable environment deterministic and aligned with the UAT
# workbook.  Both warehouses are useful for company-isolation checks.
warehouse_a = env["stock.warehouse"].search(
    [("company_id", "=", company_a.id)], limit=1
)
if warehouse_a:
    warehouse_a.write({"name": "WH-A", "code": "WHA"})
else:
    warehouse_a = env["stock.warehouse"].create({
        "name": "WH-A", "code": "WHA", "company_id": company_a.id,
    })
warehouse_b = env["stock.warehouse"].search(
    [("company_id", "=", company_b.id)], limit=1
)
if warehouse_b:
    warehouse_b.write({"name": "WH-B", "code": "WHB"})
else:
    warehouse_b = env["stock.warehouse"].create({
        "name": "WH-B", "code": "WHB", "company_id": company_b.id,
    })

company_a.write({
    "chantier_purchase_approval_threshold": 10000.0,
    "chantier_purchase_two_person": True,
    "chantier_quality_required": True,
    "chantier_consumption_control_required": True,
    "sale_chantier_followup_delay_days": 3,
})

weight_category = ref("uom.product_uom_categ_kgm")
bag_uom = env["uom.uom"].with_context(active_test=False).search(
    [("name", "=", "50 kg Bag"), ("category_id", "=", weight_category.id)],
    limit=1,
)
bag_values = {
    "name": "50 kg Bag",
    "category_id": weight_category.id,
    "uom_type": "bigger",
    "factor": 0.02,
    "rounding": 1.0,
    "active": True,
}
if bag_uom:
    bag_uom.write(bag_values)
else:
    bag_uom = env["uom.uom"].create(bag_values)


def upsert_product(name, values):
    product = env["product.template"].with_context(active_test=False).search(
        [("name", "=", name), ("company_id", "=", company_a.id)],
        limit=1,
    )
    values = {
        "name": name,
        "company_id": company_a.id,
        "sale_ok": True,
        "purchase_ok": True,
        "active": True,
        **values,
    }
    if product:
        product.write(values)
    else:
        product = env["product.template"].create(values)
    return product


unit_uom = ref("uom.product_uom_unit")
kg_uom = ref("uom.product_uom_kgm")
upsert_product(
    "Construction Service",
    {
        "type": "service",
        "uom_id": unit_uom.id,
        "uom_po_id": unit_uom.id,
        "list_price": 30000.0,
    },
)
upsert_product(
    "Cement Bag",
    {
        "type": "product",
        "uom_id": bag_uom.id,
        "uom_po_id": bag_uom.id,
        "list_price": 85.0,
        "standard_price": 70.0,
    },
)
upsert_product(
    "Steel Bar",
    {
        "type": "product",
        "uom_id": kg_uom.id,
        "uom_po_id": kg_uom.id,
        "list_price": 12.0,
        "standard_price": 9.0,
    },
)
upsert_product(
    "Paint Bucket",
    {
        "type": "product",
        "uom_id": unit_uom.id,
        "uom_po_id": unit_uom.id,
        "list_price": 450.0,
        "standard_price": 320.0,
    },
)

sales_region_plan = env["account.analytic.plan"].search(
    [("name", "=", "Sales Region")], limit=1
)
if not sales_region_plan:
    sales_region_plan = env["account.analytic.plan"].create({
        "name": "Sales Region",
    })
sales_region_account = env["account.analytic.account"].search(
    [
        ("name", "=", "Casablanca Sales"),
        ("plan_id", "=", sales_region_plan.id),
        ("company_id", "=", company_a.id),
    ],
    limit=1,
)
if not sales_region_account:
    env["account.analytic.account"].create({
        "name": "Casablanca Sales",
        "plan_id": sales_region_plan.id,
        "company_id": company_a.id,
    })

personas = [
    (
        "U1",
        "Management / Chantier Manager",
        "uat.u1.manager",
        [
            "elmokrif_chantier.group_chantier_manager",
            "elmokrif_stock_controls.group_chantier_consumption_approver",
            "elmokrif_dashboard.group_elmokrif_dashboard_user",
        ],
        [company_a],
    ),
    (
        "U2",
        "Chantier User / BOQ Estimator",
        "uat.u2.chantier",
        [
            "elmokrif_chantier.group_chantier_user",
            "elmokrif_stock_controls.group_chantier_consumption_user",
            "elmokrif_tender_boq.group_boq_estimator",
        ],
        [company_a],
    ),
    (
        "U3",
        "Buyer",
        "uat.u3.buyer",
        ["elmokrif_purchase_quality.group_chantier_purchase_buyer"],
        [company_a],
    ),
    (
        "U4",
        "Purchase Approver",
        "uat.u4.purchase.approver",
        ["elmokrif_purchase_quality.group_chantier_purchase_approver"],
        [company_a],
    ),
    (
        "U5",
        "Storekeeper",
        "uat.u5.storekeeper",
        [
            "stock.group_stock_manager",
            "elmokrif_chantier.group_chantier_user",
        ],
        [company_a],
    ),
    (
        "U6",
        "Quality Inspector",
        "uat.u6.quality",
        ["elmokrif_purchase_quality.group_chantier_quality_inspector"],
        [company_a],
    ),
    (
        "U7",
        "Salesperson",
        "uat.u7.sales",
        [
            "sales_team.group_sale_salesman",
            "elmokrif_chantier.group_chantier_sales_reader",
            "analytic.group_analytic_accounting",
        ],
        [company_a],
    ),
    (
        "U8",
        "Accountant",
        "uat.u8.accountant",
        ["account.group_account_manager"],
        [company_a],
    ),
    (
        "U9",
        "Document User",
        "uat.u9.documents",
        ["elmokrif_documents_bridge.group_elmokrif_document_user"],
        [company_a],
    ),
    (
        "U10",
        "Document Manager",
        "uat.u10.document.manager",
        ["elmokrif_documents_bridge.group_elmokrif_document_manager"],
        [company_a],
    ),
    (
        "U11",
        "Employee",
        "uat.u11.employee",
        ["elmokrif_hr_extension.group_hr_employee"],
        [company_a],
    ),
    (
        "U12",
        "HR Officer / Manager",
        "uat.u12.hr.manager",
        ["elmokrif_hr_extension.group_hr_manager"],
        [company_a],
    ),
    (
        "U13",
        "Dashboard User",
        "uat.u13.dashboard",
        ["elmokrif_dashboard.group_elmokrif_dashboard_user"],
        [company_a, company_b],
    ),
    (
        "U14",
        "Other-company User",
        "uat.u14.companyb",
        [
            "elmokrif_chantier.group_chantier_user",
            "elmokrif_documents_bridge.group_elmokrif_document_user",
            "elmokrif_dashboard.group_elmokrif_dashboard_user",
        ],
        [company_b],
    ),
]

credentials = []
internal_user = ref("base.group_user")
for code, role, login, group_xmlids, companies in personas:
    new_password = SHARED_PASSWORD
    groups = internal_user | env["res.groups"].browse(
        [ref(xmlid).id for xmlid in group_xmlids]
    )
    company_ids = [company.id for company in companies]
    values = {
        "name": f"{code} - {role}",
        "login": login,
        "email": f"{login}@example.test",
        "active": True,
        "company_id": companies[0].id,
        "company_ids": [(6, 0, company_ids)],
        "groups_id": [(6, 0, groups.ids)],
        "password": new_password,
        "lang": "en_US",
    }
    user = env["res.users"].with_context(no_reset_password=True).search(
        [("login", "=", login)], limit=1
    )
    if user:
        user.with_context(no_reset_password=True).write(values)
    else:
        user = env["res.users"].with_context(no_reset_password=True).create(values)
    credentials.append((code, role, login, new_password, user.id))

admin = ref("base.user_admin")
admin_password = SHARED_PASSWORD
admin.write(
    {
        "name": "UAT Administrator",
        "login": "uat.admin",
        "email": "uat.admin@example.test",
        "password": admin_password,
        "company_id": company_a.id,
        "company_ids": [(6, 0, [company_a.id, company_b.id])],
    }
)
env["hr.employee"].search([("user_id", "=", admin.id)]).unlink()

user_u11 = env["res.users"].search([("login", "=", "uat.u11.employee")], limit=1)
user_u12 = env["res.users"].search([("login", "=", "uat.u12.hr.manager")], limit=1)
user_u7 = env["res.users"].search([("login", "=", "uat.u7.sales")], limit=1)
employee_u12 = env["hr.employee"].search([("user_id", "=", user_u12.id)], limit=1)
if not employee_u12:
    employee_u12 = env["hr.employee"].create(
        {
            "name": "U12 - HR Officer / Manager",
            "user_id": user_u12.id,
            "company_id": company_a.id,
        }
    )
employee_u11 = env["hr.employee"].search([("user_id", "=", user_u11.id)], limit=1)
employee_u11_values = {
    "name": "U11 - Employee",
    "user_id": user_u11.id,
    "company_id": company_a.id,
    "parent_id": employee_u12.id,
}
if employee_u11:
    employee_u11.write(employee_u11_values)
else:
    env["hr.employee"].create(employee_u11_values)

# UAT-04 needs the sales persona to select the controlled UAT chantier while
# keeping it out of the operational chantier team and menus.
uat_chantier = env["project.project"].search(
    [
        "|",
        ("chantier_reference", "=", "CH-UAT-001"),
        ("name", "=", "CH-UAT-001"),
        ("company_id", "=", company_a.id),
    ],
    limit=1,
)
if uat_chantier and user_u7:
    uat_chantier.write({"sales_user_ids": [(4, user_u7.id)]})

# The operational personas must be explicitly assigned to the controlled UAT
# chantier.  Record rules intentionally hide chantiers from unassigned users.
if uat_chantier:
    uat_operational_users = env["res.users"].search([
        ("login", "in", [
            "uat.u2.chantier",
            "uat.u3.buyer",
            "uat.u4.purchase.approver",
            "uat.u5.storekeeper",
            "uat.u6.quality",
        ]),
    ])
    uat_chantier.write({
        "chantier_member_ids": [(4, user.id) for user in uat_operational_users],
    })

env.cr.commit()
print(f"UAT_COMPANY|A|{company_a.id}|{company_a.name}")
print(f"UAT_COMPANY|B|{company_b.id}|{company_b.name}")
print(f"UAT_ADMIN|uat.admin|{admin_password}|{admin.id}")
for code, role, login, new_password, user_id in credentials:
    print(f"UAT_CREDENTIAL|{code}|{role}|{login}|{new_password}|{user_id}")
