param(
    [string]$ProjectRoot = "",
    [string]$PolicyFile = "",
    [string]$QuarantineRoot = "",
    [switch]$Apply,
    [switch]$PurgeQuarantine
)

$ErrorActionPreference = "Stop"

if (-not $ProjectRoot) {
    $ProjectRoot = (Resolve-Path (Join-Path $PSScriptRoot "..")).Path
}
$ProjectRoot = [System.IO.Path]::GetFullPath($ProjectRoot)

if (-not $PolicyFile) {
    $PolicyFile = Join-Path $ProjectRoot "config\retention_policy.json"
}
if (-not $QuarantineRoot) {
    $QuarantineRoot = Join-Path $ProjectRoot ".quarantine"
}
$QuarantineRoot = [System.IO.Path]::GetFullPath($QuarantineRoot)

if ($QuarantineRoot -eq $ProjectRoot -or $ProjectRoot.StartsWith($QuarantineRoot + [System.IO.Path]::DirectorySeparatorChar)) {
    throw "QuarantineRoot cannot be the project root or a parent of it."
}

$policy = Get-Content -Raw -LiteralPath $PolicyFile | ConvertFrom-Json
$now = Get-Date
$candidates = @()

foreach ($property in $policy.paths.PSObject.Properties) {
    $relativeDirectory = $property.Name
    $retentionDays = [int]$property.Value
    $sourceDirectory = [System.IO.Path]::GetFullPath((Join-Path $ProjectRoot $relativeDirectory))

    if (-not $sourceDirectory.StartsWith($ProjectRoot + [System.IO.Path]::DirectorySeparatorChar)) {
        throw "Retention path escapes ProjectRoot: $relativeDirectory"
    }
    if (-not (Test-Path -LiteralPath $sourceDirectory)) { continue }

    $cutoff = $now.AddDays(-$retentionDays)
    Get-ChildItem -LiteralPath $sourceDirectory -File -Recurse -Force | Where-Object {
        $_.LastWriteTime -lt $cutoff
    } | ForEach-Object {
        $relativePath = $_.FullName.Substring($ProjectRoot.Length).TrimStart(
            [System.IO.Path]::DirectorySeparatorChar,
            [System.IO.Path]::AltDirectorySeparatorChar
        )
        $candidates += [pscustomobject]@{
            Source = $_.FullName
            RelativePath = $relativePath
            LastWriteTime = $_.LastWriteTime
            RetentionDays = $retentionDays
        }
    }
}

if (-not $Apply) {
    $candidates | Sort-Object Source | Format-Table RelativePath, LastWriteTime, RetentionDays -AutoSize
    Write-Host "Dry run: $($candidates.Count) file(s) would move to quarantine. Use -Apply to move them."
    exit 0
}

foreach ($item in $candidates) {
    $destination = Join-Path $QuarantineRoot $item.RelativePath
    $destinationDirectory = Split-Path -Parent $destination
    New-Item -ItemType Directory -Force -Path $destinationDirectory | Out-Null
    Move-Item -LiteralPath $item.Source -Destination $destination -Force
}

Write-Host "Moved $($candidates.Count) expired file(s) to $QuarantineRoot"

if ($PurgeQuarantine -and (Test-Path -LiteralPath $QuarantineRoot)) {
    $quarantineCutoff = $now.AddDays(-[int]$policy.quarantine_days)
    $purgeCandidates = Get-ChildItem -LiteralPath $QuarantineRoot -File -Recurse -Force | Where-Object {
        $_.LastWriteTime -lt $quarantineCutoff
    }
    foreach ($file in $purgeCandidates) {
        Remove-Item -LiteralPath $file.FullName -Force
    }
    Write-Host "Permanently removed $($purgeCandidates.Count) expired quarantined file(s)."
}
