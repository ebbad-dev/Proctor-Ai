param(
    [string]$InstanceKey = "MSSQL17.MSSQLSERVER"
)

$ErrorActionPreference = "Stop"

$logDir = Join-Path (Split-Path -Parent $PSScriptRoot) "logs"
New-Item -ItemType Directory -Path $logDir -Force | Out-Null
Start-Transcript -Path (Join-Path $logDir "sqlserver_protocol_enable.log") -Force | Out-Null

$base = "HKLM:\SOFTWARE\Microsoft\Microsoft SQL Server\$InstanceKey\MSSQLServer\SuperSocketNetLib"
$tcp = Join-Path $base "Tcp"
$np = Join-Path $base "Np"

Set-ItemProperty -Path $tcp -Name Enabled -Value 1
Set-ItemProperty -Path $np -Name Enabled -Value 1

Restart-Service -Name MSSQLSERVER -Force
Start-Sleep -Seconds 8

Get-Service MSSQLSERVER | Select-Object Name, Status
Get-ItemProperty $tcp | Select-Object @{n = "Protocol"; e = { "Tcp" } }, Enabled, ListenOnAllIPs
Get-ItemProperty $np | Select-Object @{n = "Protocol"; e = { "NamedPipes" } }, Enabled, PipeName

Stop-Transcript | Out-Null
