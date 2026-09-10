{
    "name": "EL MOKRIF Chantier Estimation",
    "summary": "Construction quantities, resource costs, logistics, and phased cash flow",
    "version": "17.0.1.0.0",
    "category": "Construction",
    "author": "EL MOKRIF",
    "license": "LGPL-3",
    "depends": ["elmokrif_chantier_stock", "elmokrif_purchase_quality", "elmokrif_sale_chantier", "account"],
    "data": [
        "security/ir.model.access.csv",
        "data/cost_code_data.xml",
        "security/estimation_rules.xml",
        "views/estimation_views.xml",
        "views/daily_report_views.xml",
        "views/project_project_views.xml",
    ],
    "installable": True,
    "application": True,
}
