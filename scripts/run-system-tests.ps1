param([string]$Database = "soloodoo_system_test")

$modules = "elmokrif_chantier,elmokrif_chantier_stock,elmokrif_chantier_estimation,elmokrif_purchase_quality,elmokrif_sale_chantier,elmokrif_finance_readiness,elmokrif_crm,elmokrif_documents_bridge,elmokrif_calendar_bridge,elmokrif_stock_controls,elmokrif_dashboard,elmokrif_finance_operations,elmokrif_hr_extension,elmokrif_integration_tests"

& (Join-Path $PSScriptRoot "run-isolated-tests.ps1") `
    -Database $Database `
    -Modules $modules `
    -Suite "system"
if ($LASTEXITCODE -ne 0) { exit $LASTEXITCODE }
