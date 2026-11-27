param(
    [string]$ProjectRoot = "",
    [string]$PythonExe = ""
)

$ErrorActionPreference = "Stop"

if (-not $ProjectRoot) {
    $ProjectRoot = (Resolve-Path (Join-Path $PSScriptRoot "..")).Path
}
if (-not $PythonExe) {
    $PythonExe = Join-Path $ProjectRoot ".venv\Scripts\python.exe"
}

$logDir = Join-Path $ProjectRoot "logs"
New-Item -ItemType Directory -Path $logDir -Force | Out-Null
$logPath = Join-Path $logDir "sqlserver_live_smoke.log"

Set-Location $ProjectRoot
$env:PYTHONPATH = Join-Path $ProjectRoot "python_user_deps"

"=== ProctorAI SQL Server Smoke $(Get-Date -Format o) ===" | Set-Content -Path $logPath
& $PythonExe (Join-Path $ProjectRoot "scripts\sqlserver_live_smoke.py") *>&1 | Tee-Object -FilePath $logPath -Append
exit $LASTEXITCODE
