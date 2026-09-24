{
    "name": "EL MOKRIF Stock Controls",
    "summary": "Approved chantier consumption with source-linked stock effects",
    "version": "17.0.1.0.0",
    "category": "Inventory/Inventory",
    "author": "EL MOKRIF",
    "license": "LGPL-3",
    "depends": ["elmokrif_chantier_stock"],
    "data": [
        "security/stock_control_groups.xml",
        "security/ir.model.access.csv",
        "security/stock_control_rules.xml",
        "views/consumption_views.xml",
        "views/res_company_views.xml",
    ],
    "installable": True,
    "application": True,
}
