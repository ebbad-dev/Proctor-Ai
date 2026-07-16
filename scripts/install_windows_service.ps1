param(
    [string]$ProjectRoot = "C:\Users\HP\OneDrive\Desktop\My Projects\Proctor AI",
    [string]$ServiceName = "ProctorAI",
    [string]$NssmPath = "",
    [string]$NodeExe = "",
    [switch]$Uninstall
)

$ErrorActionPreference = "Stop"

if (-not $NssmPath) {
    $NssmPath = if ($env:NSSM_PATH) { $env:NSSM_PATH } else { "nssm" }
}
if (-not $NodeExe) {
    $NodeExe = if ($env:NODE_EXE) { $env:NODE_EXE } else { "node" }
}

$nssmCommand = Get-Command $NssmPath -ErrorAction SilentlyContinue
if (-not $nssmCommand) {
    throw "NSSM was not found. Install NSSM and set NSSM_PATH, or use scripts/install_windows_scheduled_task.ps1 instead."
}

if ($Uninstall) {
    Write-Host "Stopping and removing Windows service '$ServiceName'."
    & $NssmPath stop $ServiceName
    & $NssmPath remove $ServiceName confirm
    exit $LASTEXITCODE
}

$launcher = Join-Path $ProjectRoot "launch_proctorai.js"
if (-not (Test-Path -LiteralPath $launcher)) {
    throw "Could not find launcher: $launcher"
}

New-Item -ItemType Directory -Path (Join-Path $ProjectRoot "logs") -Force | Out-Null

Write-Host "Installing Windows service '$ServiceName'. Run this script from an elevated PowerShell prompt."
& $NssmPath install $ServiceName $NodeExe $launcher
& $NssmPath set $ServiceName AppDirectory $ProjectRoot
& $NssmPath set $ServiceName Start SERVICE_AUTO_START
& $NssmPath set $ServiceName AppStdout (Join-Path $ProjectRoot "logs\service.out.log")
& $NssmPath set $ServiceName AppStderr (Join-Path $ProjectRoot "logs\service.err.log")
& $NssmPath set $ServiceName AppRotateFiles 1
& $NssmPath set $ServiceName AppRotateBytes 10485760

Write-Host "Service installed. Start it with: nssm start $ServiceName"
