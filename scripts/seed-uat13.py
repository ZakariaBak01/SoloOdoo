"""Seed the controlled-document UAT scenario in an Odoo shell.

Run by piping this file into ``odoo shell -d <database> --no-http`` after
``provision-uat-users.py``. The script is idempotent for the named fixtures.
"""

import base64
import os
from datetime import timedelta

from odoo import Command, fields


def require(record, message):
    if not record:
        raise RuntimeError(message)
    return record


def minimal_pdf(title, body):
    text = f"{title} - {body}"
    escaped = text.replace("\\", "\\\\").replace("(", "\\(").replace(")", "\\)")
    stream = f"BT /F1 11 Tf 54 720 Td ({escaped}) Tj ET".encode()
    objects = [
        b"<</Type/Catalog/Pages 2 0 R>>",
        b"<</Type/Pages/Kids[3 0 R]/Count 1>>",
        b"<</Type/Page/Parent 2 0 R/MediaBox[0 0 612 792]/Contents 4 0 R/Resources<</Font<</F1 5 0 R>>>>>>",
        b"<</Length " + str(len(stream)).encode() + b">>stream\n" + stream + b"\nendstream",
        b"<</Type/Font/Subtype/Type1/BaseFont/Helvetica>>",
    ]
    payload = bytearray(b"%PDF-1.4\n")
    offsets = [0]
    for number, content in enumerate(objects, 1):
        offsets.append(len(payload))
        payload.extend(f"{number} 0 obj\n".encode() + content + b"\nendobj\n")
    xref_offset = len(payload)
    payload.extend(f"xref\n0 {len(objects) + 1}\n".encode())
    payload.extend(b"0000000000 65535 f \n")
    for offset in offsets[1:]:
        payload.extend(f"{offset:010d} 00000 n \n".encode())
    payload.extend(
        f"trailer<</Root 1 0 R/Size {len(objects) + 1}>>\nstartxref\n{xref_offset}\n%%EOF\n".encode()
    )
    return base64.b64encode(bytes(payload))


company_a = require(
    env["res.company"].search([("name", "=", "EL MOKRIF COMPANY SARL")], limit=1),
    "Company A is missing; run provision-uat-users.py first.",
)
company_b = require(
    env["res.company"].search([("name", "=", "UAT ISOLATION COMPANY B")], limit=1),
    "Company B is missing; run provision-uat-users.py first.",
)
u1 = require(env["res.users"].search([("login", "=", "uat.u1.manager")], limit=1), "U1 is missing.")
u9 = require(env["res.users"].search([("login", "=", "uat.u9.documents")], limit=1), "U9 is missing.")
u10 = require(env["res.users"].search([("login", "=", "uat.u10.document.manager")], limit=1), "U10 is missing.")
u14 = require(env["res.users"].search([("login", "=", "uat.u14.companyb")], limit=1), "U14 is missing.")
customer = require(env["res.partner"].search([
    ("name", "=", "UAT Customer A"), ("company_id", "=", company_a.id),
], limit=1), "UAT Customer A is missing.")
site = require(env["res.partner"].search([
    ("name", "=", "UAT Customer A Site"), ("company_id", "=", company_a.id),
], limit=1), "UAT Customer A Site is missing.")
warehouse = require(env["stock.warehouse"].search([
    ("company_id", "=", company_a.id),
], limit=1), "Company A warehouse is missing.")

# The UAT playbook uses this exact reference. A fresh database has not consumed
# the chantier sequence yet, so make its first value deterministic.
chantier = env["project.project"].with_context(active_test=False).search([
    "|", ("chantier_reference", "=", "CH-UAT-001"), ("name", "=", "CH-UAT-001"),
    ("company_id", "=", company_a.id),
], limit=1)
if not chantier:
    sequence = require(env["ir.sequence"].search([
        ("code", "=", "elmokrif.chantier"),
        "|", ("company_id", "=", False), ("company_id", "=", company_a.id),
    ], limit=1), "Chantier sequence is missing.")
    sequence.write({"prefix": "CH-UAT-", "padding": 3, "number_next_actual": 1})
    chantier = env["project.project"].with_company(company_a).create({
        "name": "CH-UAT-001",
        "is_chantier": True,
        "company_id": company_a.id,
        "partner_id": customer.id,
        "site_partner_id": site.id,
        "warehouse_id": warehouse.id,
        "chantier_region": "Casablanca-Settat",
        "work_type": "construction",
        "user_id": u1.id,
        "chantier_member_ids": [Command.set([u9.id, u10.id])],
        "date_start": fields.Date.today(),
        "date": fields.Date.today() + timedelta(days=90),
        "privacy_visibility": "followers",
    })
    chantier.with_user(u1).action_approve_chantier()
    chantier.with_user(u1).action_start_chantier()
else:
    chantier.write({"chantier_member_ids": [Command.link(u9.id), Command.link(u10.id)]})

# A same-company document user without chantier assignment proves that Company
# A membership alone does not grant controlled-document access.
unrelated_login = "uat.u9.unrelated"
unrelated = env["res.users"].with_context(active_test=False).search([
    ("login", "=", unrelated_login),
], limit=1)
unrelated_values = {
    "name": "U9B - Unrelated Document User",
    "login": unrelated_login,
    "email": f"{unrelated_login}@example.test",
    "active": True,
    "company_id": company_a.id,
    "company_ids": [Command.set([company_a.id])],
    "groups_id": [Command.set([
        env.ref("base.group_user").id,
        env.ref("elmokrif_documents_bridge.group_elmokrif_document_user").id,
    ])],
    "password": os.environ.get("UAT_SHARED_PASSWORD", "UAT2026!"),
    "lang": "en_US",
}
if unrelated:
    unrelated.with_context(no_reset_password=True).write(unrelated_values)
else:
    unrelated = env["res.users"].with_context(no_reset_password=True).create(unrelated_values)


def upsert_upload(name, title, body):
    attachment = env["ir.attachment"].with_user(u9).search([
        ("name", "=", name), ("res_model", "=", False), ("res_id", "=", 0),
    ], limit=1)
    values = {
        "name": name,
        "mimetype": "application/pdf",
        "datas": minimal_pdf(title, body),
        "company_id": company_a.id,
        "public": False,
    }
    if attachment:
        attachment.write(values)
    else:
        attachment = env["ir.attachment"].with_user(u9).create(values)
    return attachment


upload_v1 = upsert_upload(
    "uat-contract-v1.pdf",
    "UAT Construction Contract - Revision 1",
    "Draft evidence for rejection and corrected resubmission testing.",
)
upload_v2 = upsert_upload(
    "uat-contract-v2.pdf",
    "UAT Construction Contract - Revision 2",
    "Replacement evidence for controlled revision approval testing.",
)


def ensure_expiry_fixture(name, expiry_date):
    document = env["elmokrif.document"].search([
        ("name", "=", name), ("company_id", "=", company_a.id),
    ], limit=1)
    if document:
        return document
    attachment = env["ir.attachment"].with_user(u9).create({
        "name": f"{name.lower().replace(' ', '-')}.pdf",
        "mimetype": "application/pdf",
        "datas": minimal_pdf(name, "Approved fixture for idempotent expiry-reminder testing."),
        "company_id": company_a.id,
    })
    document = env["elmokrif.document"].with_user(u9).create({
        "name": name,
        "company_id": company_a.id,
        "chantier_id": chantier.id,
        "category": "certificate",
        "owner_id": u9.id,
        "issue_date": fields.Date.today() - timedelta(days=30),
        "expiry_date": expiry_date,
        "attachment_id": attachment.id,
    })
    document.with_user(u9).action_submit_for_review()
    document.with_user(u10).action_approve()
    return document


near_expiry = ensure_expiry_fixture(
    "UAT Near Expiry Control", fields.Date.today() + timedelta(days=5),
)
past_expiry = ensure_expiry_fixture(
    "UAT Past Expiry Control", fields.Date.today() - timedelta(days=1),
)

env.cr.commit()
print(f"UAT13_CHANTIER|{chantier.id}|{chantier.chantier_reference}|{chantier.chantier_state}")
print(f"UAT13_UPLOAD|v1|{upload_v1.id}|{upload_v1.name}")
print(f"UAT13_UPLOAD|v2|{upload_v2.id}|{upload_v2.name}")
print(f"UAT13_EXPIRY|near|{near_expiry.id}|{near_expiry.expiry_date}")
print(f"UAT13_EXPIRY|past|{past_expiry.id}|{past_expiry.expiry_date}")
print(f"UAT13_ISOLATION|same_company|{unrelated.login}|other_company|{u14.login}")
