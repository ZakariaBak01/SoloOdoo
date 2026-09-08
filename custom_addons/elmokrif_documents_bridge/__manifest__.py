{
    "name": "EL MOKRIF Documents Bridge",
    "summary": "Controlled chantier document revisions, approvals and expiry activities",
    "version": "17.0.1.0.0",
    "category": "Document Management",
    "author": "EL MOKRIF",
    "license": "LGPL-3",
    "depends": ["mail", "elmokrif_chantier"],
    "data": [
        "security/document_groups.xml",
        "security/ir.model.access.csv",
        "security/document_rules.xml",
        "views/document_views.xml",
        "data/document_cron.xml",
    ],
    "installable": True,
    "application": True,
}
