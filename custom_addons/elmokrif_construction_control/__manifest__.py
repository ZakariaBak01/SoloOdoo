{
    "name": "EL MOKRIF Construction Control",
    "summary": "Work packages, RFIs, submittals, changes, progress certification, and project controls",
    "version": "17.0.1.0.0",
    "category": "Construction",
    "author": "EL MOKRIF",
    "license": "LGPL-3",
    "depends": [
        "elmokrif_tender_boq",
        "elmokrif_dashboard",
        "sale_management",
        "account",
    ],
    "data": [
        "security/construction_control_groups.xml",
        "security/ir.model.access.csv",
        "security/construction_control_rules.xml",
        "data/construction_control_sequences.xml",
        "views/construction_control_views.xml",
        "views/integration_views.xml",
        "views/construction_control_menus.xml",
    ],
    "installable": True,
    "application": True,
}

