param([string]$Database = "soloodoo_browser_test")

& (Join-Path $PSScriptRoot "run-isolated-tests.ps1") -Database $Database -Modules "elmokrif_browser_tests" -Suite "browser" -Dockerfile "Dockerfile.test"
if ($LASTEXITCODE -ne 0) { exit $LASTEXITCODE }
