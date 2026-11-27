param(
    [Parameter(Mandatory = $true)]
    [string]$BackupFile,
    [string]$Server = "localhost",
    [string]$Database = "ProctorAI_Lite",
    [string]$SqlcmdPath = "sqlcmd",
    [switch]$ConfirmRestore,
    # sqlcmd 18 rejects the self-signed certificate of a local SQL Server unless -C is passed.
    # Use -StrictCertificate when the server presents a CA-trusted certificate.
    [switch]$StrictCertificate
)

$ErrorActionPreference = "Stop"

if (-not (Test-Path -LiteralPath $BackupFile)) {
    throw "Backup file was not found: $BackupFile"
}

if (-not $ConfirmRestore) {
    throw "Restore is destructive. Re-run with -ConfirmRestore after verifying the backup target."
}

$fullPath = (Resolve-Path -LiteralPath $BackupFile).Path
$escapedPath = $fullPath.Replace("'", "''")

$sql = @"
ALTER DATABASE [$Database] SET SINGLE_USER WITH ROLLBACK IMMEDIATE;
RESTORE DATABASE [$Database]
FROM DISK = N'$escapedPath'
WITH REPLACE, STATS = 10;
ALTER DATABASE [$Database] SET MULTI_USER;
"@

Write-Host "Restoring '$Database' on '$Server' from:"
Write-Host $fullPath
$sqlcmdArgs = @("-S", $Server, "-E", "-b")
if (-not $StrictCertificate) { $sqlcmdArgs += "-C" }
& $SqlcmdPath @sqlcmdArgs -Q $sql

if ($LASTEXITCODE -ne 0) {
    throw "sqlcmd restore failed with exit code $LASTEXITCODE"
}

Write-Host "Restore complete."
