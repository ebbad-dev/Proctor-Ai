param(
    [string]$ProjectRoot = "C:\Users\HP\OneDrive\Desktop\My Projects\Proctor AI",
    [string]$PythonExe = "C:\Users\HP\.cache\codex-runtimes\codex-primary-runtime\dependencies\python\python.exe",
    [string]$LogPath = ""
)

$ErrorActionPreference = "Continue"

if (-not $LogPath) {
    $LogPath = Join-Path $ProjectRoot "logs\sqlserver_live_smoke.log"
}

New-Item -ItemType Directory -Path (Split-Path -Parent $LogPath) -Force | Out-Null
Set-Content -Path $LogPath -Value "=== ProctorAI SQL Server Smoke $(Get-Date -Format o) ==="

try {
    Set-Location $ProjectRoot
    $env:PYTHONPATH = "$ProjectRoot;$($ProjectRoot)\python_user_deps"
    Add-Content -Path $LogPath -Value "Running as: $([System.Security.Principal.WindowsIdentity]::GetCurrent().Name)"
    Add-Content -Path $LogPath -Value "Python: $PythonExe"
    & $PythonExe (Join-Path $ProjectRoot "scripts\sqlserver_live_smoke.py") *>&1 | Tee-Object -FilePath $LogPath -Append
    Add-Content -Path $LogPath -Value "ExitCode: $LASTEXITCODE"
    if ($LASTEXITCODE -ne 0) {
        exit $LASTEXITCODE
    }
} catch {
    Add-Content -Path $LogPath -Value "ERROR: $($_.Exception.Message)"
    exit 1
}
