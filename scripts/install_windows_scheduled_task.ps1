param(
    [string]$ProjectRoot = "C:\Users\HP\OneDrive\Desktop\My Projects\Proctor AI",
    [string]$TaskName = "ProctorAI",
    [string]$UserId = "",
    [switch]$Uninstall
)

$ErrorActionPreference = "Stop"

if ($Uninstall) {
    Unregister-ScheduledTask -TaskName $TaskName -Confirm:$false
    Write-Host "Scheduled task removed: $TaskName"
    exit 0
}

$scriptPath = Join-Path $ProjectRoot "scripts\start_production.ps1"
if (-not (Test-Path -LiteralPath $scriptPath)) {
    throw "Could not find production start script: $scriptPath"
}

$argument = "-NoProfile -ExecutionPolicy Bypass -File `"$scriptPath`""
$action = New-ScheduledTaskAction -Execute "powershell.exe" -Argument $argument -WorkingDirectory $ProjectRoot
$trigger = New-ScheduledTaskTrigger -AtLogOn

if (-not $UserId) {
    $UserId = [System.Security.Principal.WindowsIdentity]::GetCurrent().Name
}

$principal = New-ScheduledTaskPrincipal -UserId $UserId -LogonType Interactive -RunLevel Highest
$settings = New-ScheduledTaskSettingsSet -AllowStartIfOnBatteries -DontStopIfGoingOnBatteries -RestartCount 3 -RestartInterval (New-TimeSpan -Minutes 1)

Register-ScheduledTask -TaskName $TaskName -Action $action -Trigger $trigger -Principal $principal -Settings $settings -Force | Out-Null
Write-Host "Scheduled task installed: $TaskName"
Write-Host "Start manually with: Start-ScheduledTask -TaskName $TaskName"
