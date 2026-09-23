from datetime import date, timedelta

c = env["project.project"].search([("name", "=", "Atlas Marina Residence")], limit=1)
boq = env["construction.boq"].search([("chantier_id", "=", c.id)], limit=1)
unit = env.ref("uom.product_uom_unit")
supplier = env["res.partner"].search([("name", "=", "Maroc Matériaux")], limit=1)
currency = c.company_id.currency_id

if boq and not boq.line_ids:
    structure = env["construction.boq.wbs"].create({"boq_id": boq.id, "code": "03", "name": "Concrete Structure"})
    finishes = env["construction.boq.wbs"].create({"boq_id": boq.id, "code": "09", "name": "Architectural Finishes"})
    env["construction.boq.line"].create([
        {"boq_id": boq.id, "section_id": structure.id, "item_code": "03.10.10", "description": "Reinforced concrete podium slab", "uom_id": unit.id, "quantity_method": "manual", "quantity": 420, "target_unit_rate": 1250, "contract_unit_rate": 1250},
        {"boq_id": boq.id, "section_id": structure.id, "item_code": "03.20.20", "description": "High-yield reinforcement steel", "uom_id": unit.id, "quantity_method": "manual", "quantity": 250, "target_unit_rate": 980, "contract_unit_rate": 980},
        {"boq_id": boq.id, "section_id": finishes.id, "item_code": "09.40.10", "description": "Lobby premium finish allowance", "uom_id": unit.id, "quantity_method": "manual", "quantity": 1, "target_unit_rate": 185000, "contract_unit_rate": 185000},
    ])

tender = env["construction.tender"].search([("chantier_id", "=", c.id)], limit=1)
if tender and not tender.bid_ids:
    bid = env["construction.tender.bid"].create({"tender_id": tender.id, "partner_id": supplier.id, "currency_id": currency.id})
    for line in boq.line_ids:
        env["construction.tender.bid.line"].create({"bid_id": bid.id, "boq_line_id": line.id, "quoted_quantity": line.quantity, "uom_id": line.uom_id.id, "quoted_unit_rate": line.contract_unit_rate * .96})

request = env["chantier.material.request"].search([("chantier_id", "=", c.id)], limit=1)
if request and request.state == "submitted":
    request.action_approve()
env.cr.commit()
print("CLIENT_DEMO_DETAIL_READY", c.id, boq.id, len(boq.line_ids), tender.id if tender else 0)
