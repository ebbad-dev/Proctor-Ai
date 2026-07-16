param(
    [string]$ProjectRoot = "C:\Users\HP\OneDrive\Desktop\My Projects\Proctor AI",
    [string]$EnvFile = "",
    [switch]$BuildFrontend
)

$ErrorActionPreference = "Stop"

Set-Location $ProjectRoot

function Import-EnvFile([string]$Path) {
    if (-not (Test-Path -LiteralPath $Path)) { return }
    Get-Content -LiteralPath $Path | ForEach-Object {
        $line = $_.Trim()
        if (-not $line -or $line.StartsWith("#") -or -not $line.Contains("=")) { return }
        $key, $value = $line.Split("=", 2)
        if ($key) {
            [Environment]::SetEnvironmentVariable($key.Trim(), $value.Trim().Trim('"').Trim("'"), "Process")
        }
    }
}

if (-not $EnvFile) {
    $EnvFile = if (Test-Path ".env.production") { ".env.production" } else { ".env" }
}
Import-EnvFile $EnvFile

$env:PYTHONPATH = "$ProjectRoot;$ProjectRoot\python_user_deps;$env:PYTHONPATH"
if (-not $env:PYTHON_EXE) {
    $localVenv = Join-Path $ProjectRoot ".venv\Scripts\python.exe"
    $codexPython = "C:\Users\HP\.cache\codex-runtimes\codex-primary-runtime\dependencies\python\python.exe"
    if (Test-Path $localVenv) {
        $env:PYTHON_EXE = $localVenv
    }
    elseif (Test-Path $codexPython) {
        $env:PYTHON_EXE = $codexPython
    }
    elseif (Get-Command py -ErrorAction SilentlyContinue) {
        $env:PYTHON_EXE = "py"
    }
    elseif (Get-Command python -ErrorAction SilentlyContinue) {
        $env:PYTHON_EXE = "python"
    }
}

if (-not $env:PYTHON_EXE) {
    throw "Python was not found. Set PYTHON_EXE in .env.production or create .venv\Scripts\python.exe."
}

New-Item -ItemType Directory -Path "logs", "runtime", "reports", "screenshots", "exports" -Force | Out-Null

if ($BuildFrontend) {
    Push-Location "frontend"
    npm.cmd run build -- --logLevel error
    Pop-Location
}

$node = if ($env:NODE_EXE) { $env:NODE_EXE } else { "node" }
Write-Host "Starting ProctorAI from $ProjectRoot"
Write-Host "Environment file: $EnvFile"
Write-Host "Python: $env:PYTHON_EXE"
& $node "launch_proctorai.js"
