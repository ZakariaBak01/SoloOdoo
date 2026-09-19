{
    "name": "EL MOKRIF Chantier",
    "summary": "Chantier lifecycle and stock-location foundation",
    "version": "17.0.1.14.0",
    "category": "Services/Project",
    "author": "EL MOKRIF",
    "license": "LGPL-3",
    "depends": ["project", "analytic", "stock", "mail", "account"],
    "data": [
        "security/chantier_groups.xml",
        "security/menu_security.xml",
        "security/ir.model.access.csv",
        "security/chantier_rules.xml",
        "data/analytic_plan_data.xml",
        "data/chantier_sequence.xml",
        "data/chantier_health_cron.xml",
        "views/project_project_views.xml",
        "views/project_task_views.xml",
    ],
    "assets": {
        "web.assets_backend": [
            "elmokrif_chantier/static/src/js/friendly_access_error.js",
            "elmokrif_chantier/static/src/js/chantier_task_kanban.js",
            "elmokrif_chantier/static/src/xml/chantier_task_kanban.xml",
        ],
    },
    "installable": True,
    "application": True,
}
