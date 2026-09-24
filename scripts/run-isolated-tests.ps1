param(
    [Parameter(Mandatory = $true)][string]$Database,
    [Parameter(Mandatory = $true)][string]$Modules,
    [ValidateSet("system", "browser")][string]$Suite = "system",
    [string]$Dockerfile = "Dockerfile",
    [string]$TestTags
)

$ErrorActionPreference = "Stop"
if ($Database -notmatch '^soloodoo_[A-Za-z0-9_]*test[A-Za-z0-9_]*$') {
    throw "Use a soloodoo_ database name containing test."
}
if ($Modules -notmatch '^elmokrif_[a-z_]+(,elmokrif_[a-z_]+)*$') {
    throw "Modules must be comma-separated EL MOKRIF addon names."
}
$docker = (Get-Command docker -ErrorAction SilentlyContinue).Source
if (-not $docker) {
    $docker = Join-Path $env:LOCALAPPDATA "Programs\DockerDesktop\resources\bin\docker.exe"
}
if (-not (Test-Path -LiteralPath $docker)) { throw "Docker CLI was not found." }

$workspace = (Resolve-Path -LiteralPath (Join-Path $PSScriptRoot "..")).Path
$runId = (Get-Date -Format "yyyyMMdd-HHmmss") + "-" + [guid]::NewGuid().ToString("N").Substring(0, 8)
$networkName = "soloodoo-test-$runId"
$databaseContainer = "$networkName-db"
$odooContainer = "$networkName-odoo"
$testImage = "soloodoo-odoo-${Suite}-test:17.0"
$artifactDirectory = Join-Path $workspace "reports\test-artifacts\$Suite\$runId"
$logPath = Join-Path $artifactDirectory "odoo.log"
$testPassword = [guid]::NewGuid().ToString("N")
if (-not $TestTags) {
    $TestTags = (($Modules -split ',' | ForEach-Object { "/$_" }) -join ',')
}
New-Item -ItemType Directory -Path $artifactDirectory -Force | Out-Null
$networkCreated = $false
$databaseCreated = $false
$odooCreated = $false

function Assert-NativeSuccess([string]$Message) {
    if ($LASTEXITCODE -ne 0) { throw $Message }
}

try {
    # Native stderr is diagnostic output, so Docker's exit status remains the
    # authority while PowerShell handles cleanup in the finally block.
    $ErrorActionPreference = "Continue"
    & $docker build -f (Join-Path $workspace $Dockerfile) -t $testImage $workspace
    Assert-NativeSuccess "The $Suite test image build failed."
    & $docker network create --internal $networkName | Out-Null
    Assert-NativeSuccess "Could not create the isolated test network."
    $networkCreated = $true
    & $docker create --name $databaseContainer --network $networkName --network-alias test-db `
        -e POSTGRES_DB=postgres -e POSTGRES_USER=odoo_test -e POSTGRES_PASSWORD=$testPassword postgres:15 | Out-Null
    Assert-NativeSuccess "Could not create the isolated PostgreSQL container."
    $databaseCreated = $true
    & $docker start $databaseContainer | Out-Null
    Assert-NativeSuccess "Could not start the isolated PostgreSQL container."
    $ready = $false
    for ($attempt = 0; $attempt -lt 30; $attempt++) {
        & $docker exec $databaseContainer pg_isready -U odoo_test -d postgres *> $null
        if ($LASTEXITCODE -eq 0) { $ready = $true; break }
        Start-Sleep -Seconds 1
    }
    if (-not $ready) { throw "The isolated PostgreSQL server did not become ready." }
    & $docker create --name $odooContainer --network $networkName --shm-size=1g `
        -e HOST=test-db -e USER=odoo_test -e PASSWORD=$testPassword `
        $testImage odoo -d $Database -i $Modules --test-enable --test-tags $TestTags `
        --stop-after-init --without-demo=all --max-cron-threads=0 --log-level=test | Out-Null
    Assert-NativeSuccess "Could not create the isolated Odoo test container."
    $odooCreated = $true
    & $docker start $odooContainer | Out-Null
    Assert-NativeSuccess "Could not start the isolated Odoo test container."
    Write-Host "Running $Suite tests on isolated PostgreSQL. Logs: $logPath"
    $testExit = (& $docker wait $odooContainer | Select-Object -Last 1)
    Assert-NativeSuccess "Could not wait for the Odoo test container."
    & $docker logs $odooContainer 2>&1 | ForEach-Object { "$_" } | Set-Content -LiteralPath $logPath -Encoding UTF8
    & $docker cp "${odooContainer}:/tmp/odoo_tests/$Database/." $artifactDirectory 2>$null

    $log = Get-Content -LiteralPath $logPath -Raw
    $log -split "`n" | Where-Object { $_ -match 'post-tests|odoo.tests.result| ERROR | CRITICAL ' } | Write-Host
    $summaries = [regex]::Matches($log, '(\d+) failed, (\d+) error(?:\(s\)|s) of (\d+) tests')
    if ([int]$testExit -ne 0) { throw "Odoo $Suite tests failed. See $logPath" }
    if (-not $summaries.Count) { throw "No Odoo test result summary found. See $logPath" }
    $summary = $summaries[$summaries.Count - 1]
    if ([int]$summary.Groups[1].Value -ne 0 -or [int]$summary.Groups[2].Value -ne 0 -or [int]$summary.Groups[3].Value -le 0) {
        throw "Odoo did not execute a passing, nonempty test suite. See $logPath"
    }
    Write-Host "Passed $($summary.Groups[3].Value) tests. Evidence: $artifactDirectory"
}
finally {
    # Only UUID-named resources created by this invocation are removed. The
    # live compose services, ports, credentials and volumes are never used.
    $ErrorActionPreference = "Continue"
    if ($odooCreated) { & $docker rm -f -v $odooContainer | Out-Null }
    if ($databaseCreated) { & $docker rm -f -v $databaseContainer | Out-Null }
    if ($networkCreated) { & $docker network rm $networkName | Out-Null }
}
