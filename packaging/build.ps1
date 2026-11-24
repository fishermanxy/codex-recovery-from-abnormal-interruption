param(
    [string]$Python = "python"
)

$ErrorActionPreference = "Stop"
$projectRoot = Resolve-Path (Join-Path $PSScriptRoot "..")
$specPath = Join-Path $projectRoot "packaging\codex_recovery.spec"
$legacyOneFile = Join-Path $projectRoot "dist\CodexRecovery.exe"

if (Test-Path -LiteralPath $legacyOneFile) {
    Remove-Item -LiteralPath $legacyOneFile -Force
}

& $Python -m PyInstaller --clean --noconfirm $specPath
if ($LASTEXITCODE -ne 0) {
    exit $LASTEXITCODE
}

Write-Output (Join-Path $projectRoot "dist\CodexRecovery\CodexRecovery.exe")
