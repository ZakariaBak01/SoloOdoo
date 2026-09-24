param(
    [ValidatePattern('^[A-Za-z0-9_]*test[A-Za-z0-9_]*$')]
    [string]$Database = "soloodoo_uat13_test",
    [string]$SharedPassword = "UAT2026!"
)

$ErrorActionPreference = "Stop"
$workspace = (Resolve-Path -LiteralPath (Join-Path $PSScriptRoot "..")).Path
$docker = (Get-Command docker -ErrorAction SilentlyContinue).Source
if (-not $docker) {
    $docker = Join-Path $env:LOCALAPPDATA "Programs\DockerDesktop\resources\bin\docker.exe"
}
if (-not (Test-Path -LiteralPath $docker)) { throw "Docker CLI was not found." }

& $docker compose -f (Join-Path $workspace "compose.yml") build odoo
if ($LASTEXITCODE -ne 0) { throw "The Odoo image build failed." }
& $docker compose -f (Join-Path $workspace "compose.yml") up -d --force-recreate db odoo
if ($LASTEXITCODE -ne 0) { throw "The rebuilt Odoo stack did not start." }

& (Join-Path $PSScriptRoot "create-flow-test-database.ps1") `
    -Database $Database -SharedPassword $SharedPassword
if ($LASTEXITCODE -ne 0) { throw "The base UAT database setup failed." }

$dbHost = (& $docker exec odoo17 printenv HOST | Select-Object -Last 1).Trim()
$dbUser = (& $docker exec odoo17 printenv USER | Select-Object -Last 1).Trim()
$dbPassword = (& $docker exec odoo17 printenv PASSWORD | Select-Object -Last 1).Trim()
$dbArgs = @("--db_host=$dbHost", "--db_user=$dbUser", "--db_password=$dbPassword")

Get-Content -LiteralPath (Join-Path $PSScriptRoot "seed-uat13.py") -Raw |
    & $docker exec -e UAT_SHARED_PASSWORD=$SharedPassword -i odoo17 odoo shell @dbArgs -d $Database --no-http
if ($LASTEXITCODE -ne 0) { throw "UAT-13 scenario seeding failed." }

Get-Content -LiteralPath (Join-Path $PSScriptRoot "validate-uat13.py") -Raw |
    & $docker exec -i odoo17 odoo shell @dbArgs -d $Database --no-http
if ($LASTEXITCODE -ne 0) { throw "UAT-13 validation failed." }

$backupPath = Join-Path $workspace "backups\$Database-uat13-ready.dump"
$containerBackup = "/tmp/$Database-uat13-ready.dump"
& $docker exec odoo17-db pg_dump -U odoo -Fc -d $Database -f $containerBackup
if ($LASTEXITCODE -ne 0) { throw "The UAT-13 backup failed." }
& $docker cp "odoo17-db:${containerBackup}" $backupPath
if ($LASTEXITCODE -ne 0) { throw "The UAT-13 backup could not be copied." }
& $docker exec odoo17-db rm -f $containerBackup
& $docker restart odoo17 | Out-Null

Write-Host "READY|http://localhost:8069|db=$Database|login=uat.admin|password=$SharedPassword"
Write-Host "U9|uat.u9.documents|$SharedPassword"
Write-Host "U10|uat.u10.document.manager|$SharedPassword"
Write-Host "U9B|uat.u9.unrelated|$SharedPassword"
Write-Host "U14|uat.u14.companyb|$SharedPassword"
Write-Host "BACKUP|$backupPath"
