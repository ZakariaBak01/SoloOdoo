"""Normalize demo labels and complete procurement/stock dashboard inputs."""
from datetime import date, timedelta

company = env["res.company"].browse(1)
chantier = env["project.project"].search([("name", "=", "Atlas Marina Residence")], limit=1)
customer = env["res.partner"].search([("name", "=", "Atlas Developments SARL")], limit=1)
supplier = env["res.partner"].search([("name", "ilike", "Maroc Mat")], limit=1)
if not supplier:
    supplier = env["res.partner"].create({"name": "Maroc Materiaux", "supplier_rank": 1, "company_id": company.id})
else:
    supplier.write({"name": "Maroc Materiaux", "supplier_rank": 1})

estimate = env["chantier.estimation"].search([("chantier_id", "=", chantier.id)], limit=1)
if estimate:
    estimate.with_context(_estimation_workflow_token=True).write({"name": "Atlas Marina - Approved Cost Plan"})
document = env["elmokrif.document"].search([("chantier_id", "=", chantier.id)], limit=1)
if document and document.state == "draft":
    document.write({"name": "Approved Structural Drawing - Podium Slab"})

cement = env["product.product"].search([("name", "=", "Cement 50 kg")], limit=1)
steel = env["product.product"].search([("name", "=", "Reinforcement Steel")], limit=1)
po = env["purchase.order"].search([("partner_id", "=", supplier.id), ("origin", "=", "Atlas Marina demo")], limit=1)
if not po:
    po = env["purchase.order"].create({
        "partner_id": supplier.id, "company_id": company.id, "origin": "Atlas Marina demo",
        "chantier_id": chantier.id, "date_planned": date.today() + timedelta(days=5),
        "order_line": [
            (0, 0, {"product_id": cement.id, "name": "Cement 50 kg - Atlas Marina", "product_qty": 180, "price_unit": 72, "date_planned": date.today() + timedelta(days=5)}),
            (0, 0, {"product_id": steel.id, "name": "Reinforcement Steel - Atlas Marina", "product_qty": 250, "price_unit": 9.5, "date_planned": date.today() + timedelta(days=5)}),
        ],
    })
if po.state == "draft":
    po.button_confirm()

# Stock valuation seed for the management KPI.
if not env["stock.valuation.layer"].search([("description", "=", "Atlas Marina demo opening stock")], limit=1):
    env["stock.valuation.layer"].create({
        "company_id": company.id, "product_id": cement.id, "quantity": 400,
        "unit_cost": 72, "value": 28800, "remaining_qty": 400, "remaining_value": 28800,
        "description": "Atlas Marina demo opening stock",
    })

# Make the pending change and variation figures useful on the extended dashboard.
change = env["construction.change.event"].search([("chantier_id", "=", chantier.id)], limit=1)
if change and change.state == "draft":
    change.write({"estimated_cost_impact": 85000, "estimated_revenue_impact": 115000})
variation = env["construction.variation.order"].search([("chantier_id", "=", chantier.id)], limit=1)
if variation and variation.state == "draft":
    variation.write({"cost_amount": 72000, "revenue_amount": 108000})

dashboard = env["elmokrif.dashboard"].search([("company_id", "=", company.id)], limit=1)
dashboard.write({"as_of_date": date.today()})
env.cr.commit()
print("FINAL_DEMO_DATA_READY", po.id, po.state, dashboard.current_stock_value, dashboard.pending_supplier_orders)
