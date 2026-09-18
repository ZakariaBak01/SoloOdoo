"""Verify UAT-04 against the provisioned local database without keeping test orders.

Run by piping this file into ``odoo shell -d <database> --no-http``.
The transaction is always rolled back after the checks.
"""

from odoo.exceptions import AccessError, ValidationError


def require(record, message):
    if not record:
        raise RuntimeError(message)
    return record


try:
    u7 = require(
        env["res.users"].search([("login", "=", "uat.u7.sales")], limit=1),
        "U7 is missing.",
    )
    customer = require(
        env["res.partner"].search([("name", "=", "UAT Customer A")], limit=1),
        "UAT Customer A is missing.",
    )
    chantier = require(
        env["project.project"].search([
            ("name", "=", "CH-UAT-001"),
            ("company_id", "=", u7.company_id.id),
        ], limit=1),
        "CH-UAT-001 is missing.",
    )
    products = env["product.product"].search([
        ("name", "in", [
            "Construction Service",
            "Cement Bag",
            "Steel Bar",
            "Paint Bucket",
        ]),
        ("company_id", "=", u7.company_id.id),
    ])
    if set(products.mapped("name")) != {
        "Construction Service", "Cement Bag", "Steel Bar", "Paint Bucket"
    }:
        raise RuntimeError("One or more UAT-04 products are missing.")
    service = products.filtered(lambda product: product.name == "Construction Service")[:1]
    cement = products.filtered(lambda product: product.name == "Cement Bag")[:1]
    region_account = require(
        env["account.analytic.account"].search([
            ("name", "=", "Casablanca Sales"),
            ("company_id", "=", u7.company_id.id),
        ], limit=1),
        "The second analytic dimension is missing.",
    )

    if chantier.partner_id.commercial_partner_id != customer.commercial_partner_id:
        raise RuntimeError("CH-UAT-001 is not assigned to UAT Customer A.")
    if chantier not in env["project.project"].with_user(u7).search([
        ("id", "=", chantier.id),
    ]):
        raise RuntimeError("U7 cannot select CH-UAT-001.")
    if not chantier.chantier_initialized or chantier.chantier_state != "in_progress":
        raise RuntimeError("CH-UAT-001 is not initialized and In Progress.")

    try:
        env["product.template"].with_user(u7).create({"name": "Forbidden UAT product"})
    except AccessError:
        pass
    else:
        raise RuntimeError("U7 can create products but should have read-only product access.")

    ordinary = env["sale.order"].with_user(u7).create({
        "partner_id": customer.id,
        "company_id": u7.company_id.id,
        "order_line": [(0, 0, {
            "product_id": service.id,
            "product_uom_qty": 1,
        })],
    })
    ordinary.action_confirm()
    if ordinary.state != "sale" or ordinary.chantier_id:
        raise RuntimeError("The ordinary non-chantier quotation did not confirm normally.")

    project_count = env["project.project"].search_count([])
    order = env["sale.order"].with_user(u7).create({
        "partner_id": customer.id,
        "company_id": u7.company_id.id,
        "chantier_id": chantier.id,
        "order_line": [
            (0, 0, {
                "product_id": service.id,
                "product_uom_qty": 1,
                "analytic_distribution": {str(region_account.id): 100.0},
            }),
            (0, 0, {
                "product_id": cement.id,
                "product_uom_qty": 10,
            }),
        ],
    })
    distribution = order.order_line.filtered(
        lambda line: line.product_id == service
    ).analytic_distribution
    if distribution.get(str(region_account.id)) != 100.0:
        raise RuntimeError("The second analytic dimension was erased.")
    if distribution.get(str(chantier.analytic_account_id.id)) != 100.0:
        raise RuntimeError("The chantier analytic account was not allocated.")

    order.write({"state": "sent"})
    order._schedule_first_chantier_followup()
    order._schedule_first_chantier_followup()
    activities = env["mail.activity"].search([
        ("res_model", "=", "sale.order"),
        ("res_id", "=", order.id),
        ("is_chantier_followup", "=", True),
    ])
    if len(activities) != 1:
        raise RuntimeError("The J+3 process did not keep exactly one follow-up activity.")
    order.action_confirm()
    if activities.exists() or order.chantier_followup_activity_id:
        raise RuntimeError("The follow-up activity remained open after confirmation.")

    env["sale.order"].with_user(u7).create({
        "partner_id": customer.id,
        "company_id": u7.company_id.id,
        "chantier_id": chantier.id,
    })
    if env["project.project"].search_count([]) != project_count:
        raise RuntimeError("Creating another order created a duplicate chantier.")

    other_customer = env["res.partner"].create({
        "name": "UAT-04 mismatch probe",
        "customer_rank": 1,
        "company_id": u7.company_id.id,
    })
    try:
        env["sale.order"].with_user(u7).create({
            "partner_id": other_customer.id,
            "company_id": u7.company_id.id,
            "chantier_id": chantier.id,
        })
    except ValidationError:
        pass
    else:
        raise RuntimeError("A customer/chantier mismatch was accepted.")

    print("UAT04_VERIFY|PASS")
finally:
    env.cr.rollback()
