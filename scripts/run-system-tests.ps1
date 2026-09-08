param([string]$Database = "soloodoo_system_test")

$ErrorActionPreference = "Stop"
if ($Database -notmatch '^[A-Za-z][A-Za-z0-9_]*$') {
    throw "Database must contain only letters, digits, and underscores."
}
$docker = (Get-Command docker -ErrorAction SilentlyContinue).Source
if (-not $docker) {
    $docker = "C:\Users\zakar\AppData\Local\Programs\DockerDesktop\resources\bin\docker.exe"
}
if (-not (Test-Path -LiteralPath $docker)) {
    throw "Docker CLI was not found."
}

$modules = @(
    "elmokrif_chantier",
    "elmokrif_chantier_stock",
    "elmokrif_sale_chantier",
    "elmokrif_hr_extension",
    "elmokrif_purchase_quality",
    "elmokrif_finance_readiness",
    "elmokrif_finance_operations",
    "elmokrif_stock_controls",
    "elmokrif_crm",
    "elmokrif_documents_bridge",
    "elmokrif_calendar_bridge",
    "elmokrif_dashboard",
    "elmokrif_integration_tests",
    "elmokrif_browser_tests"
) -join ","
$testTags = @(
    "/elmokrif_chantier",
    "/elmokrif_chantier_stock",
    "/elmokrif_sale_chantier",
    "/elmokrif_hr_extension",
    "/elmokrif_purchase_quality",
    "/elmokrif_finance_readiness",
    "/elmokrif_finance_operations",
    "/elmokrif_stock_controls",
    "/elmokrif_crm",
    "/elmokrif_documents_bridge",
    "/elmokrif_calendar_bridge",
    "/elmokrif_dashboard",
    "/elmokrif_integration_tests",
    "/elmokrif_browser_tests"
) -join ","

try {
    & $docker compose up -d db
    if ($LASTEXITCODE -ne 0) { throw "PostgreSQL failed to start." }
    $healthy = $false
    for ($attempt = 1; $attempt -le 30; $attempt++) {
        $health = (& $docker inspect --format '{{.State.Health.Status}}' odoo17-db 2>$null | Out-String).Trim()
        if ($health -eq "healthy") {
            $healthy = $true
            break
        }
        Start-Sleep -Seconds 2
    }
    if (-not $healthy) { throw "PostgreSQL did not become healthy." }
    & $docker exec odoo17-db psql -U odoo -d postgres -c "DROP DATABASE IF EXISTS $Database WITH (FORCE);"
    if ($LASTEXITCODE -ne 0) { throw "Could not reset the system-test database." }
    & $docker build -t soloodoo-odoo:17.0 .
    if ($LASTEXITCODE -ne 0) { throw "The Odoo image build failed." }
    & $docker compose run --rm --no-deps odoo odoo `
        -d $Database -i $modules --test-enable `
        --test-tags $testTags `
        --stop-after-init --without-demo=all --max-cron-threads=0 --log-level=test
    if ($LASTEXITCODE -ne 0) { throw "Odoo system tests failed." }
}
finally {
    & $docker exec odoo17-db psql -U odoo -d postgres -c "DROP DATABASE IF EXISTS $Database WITH (FORCE);"
}
