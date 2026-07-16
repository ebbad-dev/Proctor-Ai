param(
    [string]$ProjectRoot = "C:\Users\HP\OneDrive\Desktop\My Projects\Proctor AI",
    [string]$PythonExe = "C:\Users\HP\.cache\codex-runtimes\codex-primary-runtime\dependencies\python\python.exe"
)

$ErrorActionPreference = "Stop"

$logDir = Join-Path $ProjectRoot "logs"
New-Item -ItemType Directory -Path $logDir -Force | Out-Null
$logPath = Join-Path $logDir "sqlserver_live_smoke.log"

Set-Location $ProjectRoot
$env:PYTHONPATH = Join-Path $ProjectRoot "python_user_deps"

"=== ProctorAI SQL Server Smoke $(Get-Date -Format o) ===" | Set-Content -Path $logPath
& $PythonExe (Join-Path $ProjectRoot "scripts\sqlserver_live_smoke.py") *>&1 | Tee-Object -FilePath $logPath -Append
exit $LASTEXITCODE
