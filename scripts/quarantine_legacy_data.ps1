param(
    [Parameter(Mandatory = $true)]
    [string]$ProjectRoot,
    [Parameter(Mandatory = $true)]
    [string]$QuarantineRoot,
    [switch]$Apply
)

$ErrorActionPreference = "Stop"
$ProjectRoot = [System.IO.Path]::GetFullPath($ProjectRoot)
$QuarantineRoot = [System.IO.Path]::GetFullPath($QuarantineRoot)

if (-not (Test-Path -LiteralPath (Join-Path $ProjectRoot "package.json"))) {
    throw "ProjectRoot does not look like the ProctorAI workspace: $ProjectRoot"
}
if ($QuarantineRoot -eq $ProjectRoot -or $ProjectRoot.StartsWith($QuarantineRoot + [System.IO.Path]::DirectorySeparatorChar)) {
    throw "QuarantineRoot cannot be the project root or a parent of it."
}

$targets = @(
    ".env",
    ".env.production",
    ".git",
    ".venv-lock",
    "backups",
    "e2e_artifacts",
    "exports",
    "logs",
    "reports",
    "runtime",
    "screenshots",
    "python_full_deps",
    "python_runtime_deps",
    "python_user_deps",
    "procotor-ai-main",
    "frontend\node_modules",
    "frontend\dist",
    "frontend\.tanstack",
    "__pycache__"
)

$resolvedTargets = foreach ($relativePath in $targets) {
    $source = [System.IO.Path]::GetFullPath((Join-Path $ProjectRoot $relativePath))
    if (-not $source.StartsWith($ProjectRoot + [System.IO.Path]::DirectorySeparatorChar)) {
        throw "Target escapes ProjectRoot: $relativePath"
    }
    if (Test-Path -LiteralPath $source) {
        [pscustomobject]@{ RelativePath = $relativePath; Source = $source }
    }
}

if (-not $Apply) {
    $resolvedTargets | Format-Table RelativePath, Source -AutoSize
    Write-Host "Dry run: $($resolvedTargets.Count) generated/sensitive path(s) would be moved. Use -Apply after reviewing the paths."
    exit 0
}

New-Item -ItemType Directory -Force -Path $QuarantineRoot | Out-Null
foreach ($target in $resolvedTargets) {
    $destination = Join-Path $QuarantineRoot $target.RelativePath
    $destinationParent = Split-Path -Parent $destination
    New-Item -ItemType Directory -Force -Path $destinationParent | Out-Null
    if (Test-Path -LiteralPath $destination) {
        throw "Refusing to overwrite an existing quarantine target: $destination"
    }
    Move-Item -LiteralPath $target.Source -Destination $destination
}

$manifest = @{
    created_at = (Get-Date).ToUniversalTime().ToString("o")
    source_root = $ProjectRoot
    quarantine_root = $QuarantineRoot
    moved_paths = @($resolvedTargets.RelativePath)
} | ConvertTo-Json -Depth 4
Set-Content -LiteralPath (Join-Path $QuarantineRoot "quarantine-manifest.json") -Value $manifest -Encoding UTF8
Write-Host "Quarantined $($resolvedTargets.Count) path(s) at $QuarantineRoot"
