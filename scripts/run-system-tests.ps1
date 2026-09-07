param(
    [string]$Database = "soloodoo_system_test"
)

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

$modules = "elmokrif_chantier,elmokrif_chantier_stock,elmokrif_sale_chantier,elmokrif_integration_tests"

try {
    & $docker compose up -d db
    if ($LASTEXITCODE -ne 0) { throw "PostgreSQL failed to start." }
    & $docker exec odoo17-db psql -U odoo -d postgres -c "DROP DATABASE IF EXISTS $Database WITH (FORCE);"
    if ($LASTEXITCODE -ne 0) { throw "Could not reset the system-test database." }
    & $docker build -t soloodoo-odoo:17.0 .
    if ($LASTEXITCODE -ne 0) { throw "The Odoo image build failed." }
    & $docker compose run --rm --no-deps odoo odoo `
        -d $Database -i $modules --test-enable `
        --test-tags /elmokrif_chantier,/elmokrif_chantier_stock,/elmokrif_sale_chantier,/elmokrif_integration_tests `
        --stop-after-init --without-demo=all --max-cron-threads=0 --log-level=test
    if ($LASTEXITCODE -ne 0) { throw "Odoo system tests failed." }
}
finally {
    & $docker exec odoo17-db psql -U odoo -d postgres -c "DROP DATABASE IF EXISTS $Database WITH (FORCE);"
}
