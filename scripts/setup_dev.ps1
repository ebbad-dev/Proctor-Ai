param(
    [string]$ProjectRoot = "",
    [string]$PythonCommand = "py"
)

$ErrorActionPreference = "Stop"

if (-not $ProjectRoot) {
    $ProjectRoot = (Resolve-Path (Join-Path $PSScriptRoot "..")).Path
}

$venvPath = Join-Path $ProjectRoot ".venv"
$venvPython = Join-Path $venvPath "Scripts\python.exe"
$lockFile = Join-Path $ProjectRoot "requirements.lock.txt"

if (-not (Test-Path -LiteralPath $lockFile)) {
    throw "requirements.lock.txt is missing. Regenerate the dependency lock before setup."
}

if (-not (Test-Path -LiteralPath $venvPython)) {
    if ($PythonCommand -eq "py") {
        & py -3.12 -m venv $venvPath
    }
    else {
        & $PythonCommand -m venv $venvPath
    }
    if ($LASTEXITCODE -ne 0) {
        throw "Failed to create the Python 3.12 virtual environment."
    }
}

& $venvPython -m pip install --upgrade pip
if ($LASTEXITCODE -ne 0) { throw "Failed to upgrade pip." }

& $venvPython -m pip install --require-hashes -r $lockFile
if ($LASTEXITCODE -ne 0) { throw "Failed to install the locked Python dependencies." }

Push-Location (Join-Path $ProjectRoot "frontend")
try {
    npm.cmd ci
    if ($LASTEXITCODE -ne 0) { throw "Frontend dependency installation failed." }
}
finally {
    Pop-Location
}

Write-Host "Development environment is ready at $ProjectRoot"
