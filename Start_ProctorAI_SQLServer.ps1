#Requires -RunAsAdministrator

$ErrorActionPreference = "Stop"
$root = Split-Path -Parent $MyInvocation.MyCommand.Path
$logPath = Join-Path $root "logs\sqlserver_start.log"
New-Item -ItemType Directory -Path (Split-Path -Parent $logPath) -Force | Out-Null

try {
    $service = Get-Service -Name "MSSQLSERVER" -ErrorAction Stop
    if ($service.Status -ne "Running") {
        Start-Service -Name "MSSQLSERVER"
        $service.WaitForStatus("Running", [TimeSpan]::FromSeconds(30))
    }
    $service = Get-Service -Name "MSSQLSERVER"
    "$(Get-Date -Format o) MSSQLSERVER status=$($service.Status) startType=$($service.StartType)" |
        Out-File -LiteralPath $logPath -Append -Encoding utf8
    Write-Host "SQL Server is $($service.Status). You may close this window."
} catch {
    "$(Get-Date -Format o) MSSQLSERVER start failed: $($_.Exception.Message)" |
        Out-File -LiteralPath $logPath -Append -Encoding utf8
    Write-Error $_
    exit 1
}
