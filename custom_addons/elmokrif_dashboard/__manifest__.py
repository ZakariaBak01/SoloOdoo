{
    "name": "EL MOKRIF Management Dashboard",
    "summary": "Permission-aware management KPIs with matching drill-downs",
    "version": "17.0.1.0.0",
    "category": "Reporting",
    "author": "EL MOKRIF",
    "license": "LGPL-3",
    "depends": [
        "account", "stock_account", "purchase_stock", "sale_management", "crm",
        "elmokrif_chantier_stock",
    ],
    "data": [
        "security/dashboard_groups.xml",
        "security/ir.model.access.csv",
        "security/dashboard_rules.xml",
        "views/dashboard_views.xml",
    ],
    "installable": True,
    "application": True,
    "post_init_hook": "post_init_hook",
}
