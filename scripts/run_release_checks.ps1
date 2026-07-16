param(
    [string]$ProjectRoot = ""
)

$ErrorActionPreference = "Stop"
if (-not $ProjectRoot) {
    $ProjectRoot = (Resolve-Path (Join-Path $PSScriptRoot "..")).Path
}

& (Join-Path $PSScriptRoot "run_quality_checks.ps1") -ProjectRoot $ProjectRoot
if ($LASTEXITCODE -ne 0) {
    throw "Quality checks failed with exit code $LASTEXITCODE"
}

$python = Join-Path $ProjectRoot ".venv\Scripts\python.exe"
if (-not (Test-Path -LiteralPath $python)) {
    throw "Project virtual environment not found. Run scripts/setup_dev.ps1 first."
}

& $python (Join-Path $PSScriptRoot "release_readiness.py") --production --database
if ($LASTEXITCODE -ne 0) {
    throw "Release readiness checks failed with exit code $LASTEXITCODE"
}

Write-Host "Release checks passed."
