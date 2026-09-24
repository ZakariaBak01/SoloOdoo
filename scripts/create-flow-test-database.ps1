param(
    [ValidatePattern('^[A-Za-z0-9_]*test[A-Za-z0-9_]*$')]
    [string]$Database = "test",
    [string]$SharedPassword = "UAT2026!"
)

$ErrorActionPreference = "Stop"
$workspace = (Resolve-Path -LiteralPath (Join-Path $PSScriptRoot "..")).Path
$docker = (Get-Command docker -ErrorAction SilentlyContinue).Source
if (-not $docker) {
    $docker = Join-Path $env:LOCALAPPDATA "Programs\DockerDesktop\resources\bin\docker.exe"
}
if (-not (Test-Path -LiteralPath $docker)) { throw "Docker CLI was not found." }
if (-not $SharedPassword) { throw "SharedPassword cannot be empty." }

$modules = @(
    "elmokrif_chantier",
    "elmokrif_chantier_stock",
    "elmokrif_chantier_estimation",
    "elmokrif_purchase_quality",
    "elmokrif_sale_chantier",
    "elmokrif_finance_readiness",
    "elmokrif_crm",
    "elmokrif_documents_bridge",
    "elmokrif_calendar_bridge",
    "elmokrif_stock_controls",
    "elmokrif_dashboard",
    "elmokrif_finance_operations",
    "elmokrif_hr_extension",
    "elmokrif_tender_boq",
    "elmokrif_construction_control"
) -join ","

& $docker compose -f (Join-Path $workspace "compose.yml") up -d db
if ($LASTEXITCODE -ne 0) { throw "The Odoo stack did not start." }

$existing = & $docker exec odoo17-db psql -U odoo -d postgres -Atc "SELECT 1 FROM pg_database WHERE datname = '$Database'"
if ($LASTEXITCODE -ne 0) { throw "Could not inspect PostgreSQL databases." }
if ($existing -eq "1") {
    throw "Database '$Database' already exists. This command never overwrites a database."
}

Write-Host "Creating '$Database' and installing all EL MOKRIF workflow modules..."
& $docker compose -f (Join-Path $workspace "compose.yml") run --rm odoo `
    odoo -d $Database -i $modules --without-demo=all --stop-after-init --max-cron-threads=0
if ($LASTEXITCODE -ne 0) { throw "Odoo database initialization failed." }

Write-Host "Provisioning companies, master data, controls, and UAT personas..."
$env:UAT_SHARED_PASSWORD = $SharedPassword
try {
    Get-Content -LiteralPath (Join-Path $PSScriptRoot "provision-uat-users.py") -Raw |
        & $docker compose -f (Join-Path $workspace "compose.yml") run --rm -T `
            -e UAT_SHARED_PASSWORD=$SharedPassword odoo odoo shell -d $Database --no-http
    if ($LASTEXITCODE -ne 0) { throw "UAT provisioning failed." }
} finally {
    Remove-Item Env:UAT_SHARED_PASSWORD -ErrorAction SilentlyContinue
}

Write-Host "Validating installed modules, roles, isolation, and prerequisites..."
Get-Content -LiteralPath (Join-Path $PSScriptRoot "validate-flow-test-database.py") -Raw |
    & $docker compose -f (Join-Path $workspace "compose.yml") run --rm -T `
        odoo odoo shell -d $Database --no-http
if ($LASTEXITCODE -ne 0) { throw "Flow-test database validation failed." }

$backupPath = Join-Path $workspace "backups\$Database-flow-ready.dump"
$containerBackup = "/tmp/$Database-flow-ready.dump"
& $docker exec odoo17-db pg_dump -U odoo -Fc -d $Database -f $containerBackup
if ($LASTEXITCODE -ne 0) { throw "The database was created, but its backup failed." }
& $docker cp "odoo17-db:${containerBackup}" $backupPath
if ($LASTEXITCODE -ne 0) { throw "The database was created, but its backup could not be copied." }
& $docker exec odoo17-db rm -f $containerBackup

& $docker compose -f (Join-Path $workspace "compose.yml") up -d odoo
if ($LASTEXITCODE -ne 0) { throw "The database is ready, but the Odoo web service did not start." }
Write-Host "READY|http://localhost:8069|db=$Database|login=uat.admin|password=$SharedPassword"
Write-Host "BACKUP|$backupPath"
