{
    "name": "EL MOKRIF Finance Readiness",
    "summary": "Accountant approval gate for chantier financial documents",
    "version": "17.0.1.0.0",
    "category": "Accounting/Accounting",
    "author": "EL MOKRIF",
    "license": "LGPL-3",
    "depends": [
        "l10n_ma",
        "stock_account",
        "elmokrif_sale_chantier",
        "elmokrif_purchase_quality",
    ],
    "data": [
        "security/ir.model.access.csv",
        "security/finance_readiness_rules.xml",
        "views/finance_readiness_views.xml",
        "views/account_move_views.xml",
        "views/res_company_views.xml",
    ],
    "post_init_hook": "post_init_hook",
    "installable": True,
    "application": True,
}
