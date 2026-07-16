param(
    [string]$Server = "localhost",
    [string]$Database = "ProctorAI_Lite",
    [string]$BackupDir = "",
    [string]$SqlcmdPath = "sqlcmd"
)

$ErrorActionPreference = "Stop"

function Get-SqlServerBackupDirectory {
    $registryPaths = @(
        "HKLM:\SOFTWARE\Microsoft\Microsoft SQL Server\MSSQL17.MSSQLSERVER\MSSQLServer",
        "HKLM:\SOFTWARE\Microsoft\Microsoft SQL Server\MSSQL16.MSSQLSERVER\MSSQLServer",
        "HKLM:\SOFTWARE\Microsoft\Microsoft SQL Server\MSSQL15.MSSQLSERVER\MSSQLServer"
    )

    foreach ($path in $registryPaths) {
        try {
            $value = (Get-ItemProperty -LiteralPath $path -Name BackupDirectory -ErrorAction Stop).BackupDirectory
            if ($value) { return $value }
        }
        catch {
            continue
        }
    }

    return "C:\Program Files\Microsoft SQL Server\MSSQL17.MSSQLSERVER\MSSQL\Backup"
}

if (-not $BackupDir) {
    $BackupDir = Get-SqlServerBackupDirectory
}

New-Item -ItemType Directory -Path $BackupDir -Force | Out-Null
$timestamp = Get-Date -Format "yyyyMMdd_HHmmss"
$backupPath = Join-Path (Resolve-Path $BackupDir).Path "$Database`_$timestamp.bak"
$escapedPath = $backupPath.Replace("'", "''")

$sql = @"
BACKUP DATABASE [$Database]
TO DISK = N'$escapedPath'
WITH INIT, COMPRESSION, STATS = 10;
"@

Write-Host "Backing up SQL Server database '$Database' on '$Server' to:"
Write-Host $backupPath
& $SqlcmdPath -S $Server -E -b -Q $sql

if ($LASTEXITCODE -ne 0) {
    throw "sqlcmd backup failed with exit code $LASTEXITCODE"
}

try {
    if (-not (Test-Path -LiteralPath $backupPath)) {
        Write-Warning "sqlcmd reported success, but the backup file was not visible to this user: $backupPath"
    }
}
catch {
    Write-Warning "Backup completed, but this user cannot inspect the protected backup file: $backupPath"
}

Write-Host "Backup complete: $backupPath"
