param(
    [string]$ProjectRoot = "",
    [string]$PythonExe = ""
)

$ErrorActionPreference = "Stop"

if (-not $ProjectRoot) {
    $currentDirectory = (Get-Location).Path
    if (
        (Test-Path -LiteralPath (Join-Path $currentDirectory "package.json")) -and
        (Test-Path -LiteralPath (Join-Path $currentDirectory "frontend\vite.config.ts"))
    ) {
        $ProjectRoot = $currentDirectory
    }
    else {
        $ProjectRoot = (Resolve-Path (Join-Path $PSScriptRoot "..")).Path
    }
}

function Invoke-NativeStep {
    param(
        [string]$Name,
        [scriptblock]$Command
    )

    Write-Host "== $Name =="
    & $Command
    if ($LASTEXITCODE -ne 0) {
        throw "$Name failed with exit code $LASTEXITCODE"
    }
}

Set-Location $ProjectRoot
if (-not $PythonExe) {
    $venvPython = Join-Path $ProjectRoot ".venv\Scripts\python.exe"
    if (Test-Path -LiteralPath $venvPython) {
        $PythonExe = $venvPython
    }
    elseif (Get-Command py -ErrorAction SilentlyContinue) {
        $PythonExe = "py"
    }
    elseif (Get-Command python -ErrorAction SilentlyContinue) {
        $PythonExe = "python"
    }
    else {
        throw "Python 3.12 was not found. Run scripts/setup_dev.ps1 first."
    }
}

$env:PYTHONPATH = $ProjectRoot

function Invoke-Python {
    param([Parameter(ValueFromRemainingArguments = $true)][string[]]$Arguments)
    if ($PythonExe -eq "py") {
        & py -3.12 @Arguments
    }
    else {
        & $PythonExe @Arguments
    }
}

Invoke-NativeStep "Backend compile" {
    Invoke-Python -Arguments @("-m", "compileall", "-q", "infrastructure", "input", "monitoring", "reporting", "ui", "utils", "static", "config", "core", "database", "run_proctor_engine.py", "run_fastapi_backend.py", "scripts")
}

Invoke-NativeStep "Security regression tests" {
    Invoke-Python -Arguments @("-m", "unittest", "discover", "-s", "tests", "-v")
}

Invoke-NativeStep "Release structure" {
    Invoke-Python -Arguments @("scripts/release_readiness.py")
}

Push-Location frontend
try {
    Invoke-NativeStep "Frontend typecheck" {
        npm.cmd run typecheck
    }

    Invoke-NativeStep "Frontend build" {
        npm.cmd run build -- --logLevel error
    }
}
finally {
    Pop-Location
}

Write-Host "Quality checks passed."
