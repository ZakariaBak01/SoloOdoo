"""Create a coherent, disposable EL MOKRIF client demonstration dataset.

Run with: odoo shell -d elmokrif_client_demo --no-http < scripts/seed_client_demo.py
"""
from datetime import date, timedelta


company = env.company
company.write({"name": "EL MOKRIF Construction SARL"})
country = env["res.country"].search([("code", "=", "MA")], limit=1)
customer = env["res.partner"].create({
    "name": "Atlas Developments SARL", "customer_rank": 1,
    "street": "18 Boulevard Anfa", "city": "Casablanca", "country_id": country.id,
    "phone": "+212 522 000 111", "email": "projects@atlas.example",
})
supplier = env["res.partner"].create({
    "name": "Maroc Matériaux", "supplier_rank": 1, "city": "Casablanca", "country_id": country.id,
})
site = env["res.partner"].create({
    "name": "Atlas Marina Site", "parent_id": customer.id, "type": "delivery",
    "street": "Marina District", "city": "Casablanca", "country_id": country.id,
})
warehouse = env["stock.warehouse"].search([("company_id", "=", company.id)], limit=1)
unit = env.ref("uom.product_uom_unit")
cement = env["product.product"].create({"name": "Cement 50 kg", "type": "product", "sale_ok": True, "purchase_ok": True, "standard_price": 72.0, "list_price": 90.0, "uom_id": unit.id, "uom_po_id": unit.id})
steel = env["product.product"].create({"name": "Reinforcement Steel", "type": "product", "sale_ok": True, "purchase_ok": True, "standard_price": 9.5, "list_price": 12.0, "uom_id": unit.id, "uom_po_id": unit.id})
service = env["product.product"].create({"name": "Structural Works Package", "type": "service", "sale_ok": True, "list_price": 485000.0})

chantier = env["project.project"].with_context(default_is_chantier=True).create({
    "name": "Atlas Marina Residence", "is_chantier": True, "company_id": company.id,
    "partner_id": customer.id, "site_partner_id": site.id, "user_id": env.user.id,
    "warehouse_id": warehouse.id, "chantier_region": "Casablanca-Settat", "work_type": "construction",
    "date_start": date.today() - timedelta(days=45), "date": date.today() + timedelta(days=195),
})
chantier.action_approve_chantier()
chantier.action_start_chantier()

for name, done in [("Mobilisation and permits", True), ("Foundations", True), ("Concrete structure", False), ("MEP coordination", False)]:
    task = env["project.task"].create({"name": name, "project_id": chantier.id})
    if done:
        stage = env["project.task.type"].search([("fold", "=", True)], limit=1)
        if stage:
            task.stage_id = stage

estimate = env["chantier.estimation"].create({
    "name": "Atlas Marina — Approved Cost Plan", "chantier_id": chantier.id,
    "structure_type": "concrete_slab", "length": 42, "width": 28, "depth": 0.25,
    "wastage_percent": 5, "cement_bag_cost": 72, "sand_cost_m3": 165,
    "gravel_cost_m3": 190, "water_cost_litre": 0.02, "labor_hourly_cost": 48,
    "machinery_daily_cost": 2800, "truck_trip_cost": 650, "foundation_percent": 35,
    "superstructure_percent": 45, "finishing_percent": 20, "actual_labor_hours": 390,
    "actual_machinery_cost": 34000, "actual_other_cost": 12500,
})
estimate.action_submit(); estimate.action_approve()

lead = env["crm.lead"].create({"name": "Atlas Phase II Extension", "partner_id": customer.id, "expected_revenue": 780000, "type": "opportunity", "company_id": company.id})
order = env["sale.order"].create({"partner_id": customer.id, "company_id": company.id, "chantier_id": chantier.id, "order_line": [(0, 0, {"product_id": service.id, "product_uom_qty": 1, "price_unit": 485000})]})
order.action_confirm()

env["stock.quant"]._update_available_quantity(cement, warehouse.lot_stock_id, 400)
request = env["chantier.material.request"].create({"chantier_id": chantier.id, "line_ids": [(0, 0, {"product_id": cement.id, "product_uom_qty": 180}), (0, 0, {"product_id": steel.id, "product_uom_qty": 250})]})
request.action_submit()
purchase = env["purchase.order"].create({"partner_id": supplier.id, "company_id": company.id, "chantier_id": chantier.id, "order_line": [(0, 0, {"product_id": cement.id, "product_qty": 180, "price_unit": 72}), (0, 0, {"product_id": steel.id, "product_qty": 250, "price_unit": 9.5})]})

boq = env["construction.boq"].create({"name": "Atlas Marina Contract BOQ", "title": "Atlas Marina Residence — Contract Bill of Quantities", "chantier_id": chantier.id, "purpose": "client_contract"})

env.cr.commit()
print("CLIENT_DEMO_READY", chantier.id, estimate.id, lead.id, order.id, request.id, purchase.id, boq.id)
