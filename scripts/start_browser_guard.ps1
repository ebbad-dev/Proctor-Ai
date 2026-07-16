$ErrorActionPreference = "Stop"

$root = Split-Path -Parent $PSScriptRoot
$sourceExtensionPath = Join-Path $root "browser_guard_extension"
$extensionPath = "C:\tmp\proctorai_browser_guard"
$profilePath = "C:\tmp\proctorai_browser_guard_profile"
$url = "http://127.0.0.1:8080/login"

New-Item -ItemType Directory -Force -Path $profilePath | Out-Null
New-Item -ItemType Directory -Force -Path $extensionPath | Out-Null
Copy-Item -Path (Join-Path $sourceExtensionPath "*") -Destination $extensionPath -Recurse -Force

$candidates = @(
  "$env:ProgramFiles\Google\Chrome\Application\chrome.exe",
  "$env:ProgramFiles(x86)\Google\Chrome\Application\chrome.exe",
  "$env:LOCALAPPDATA\Google\Chrome\Application\chrome.exe",
  "$env:ProgramFiles\Microsoft\Edge\Application\msedge.exe",
  "$env:ProgramFiles(x86)\Microsoft\Edge\Application\msedge.exe"
)

$browser = $candidates | Where-Object { Test-Path $_ } | Select-Object -First 1
if (-not $browser) {
  throw "Chrome or Edge was not found. Install Chrome/Edge or load browser_guard_extension manually."
}

Start-Process -FilePath $browser -ArgumentList @(
  "--user-data-dir=$profilePath",
  "--load-extension=$extensionPath",
  "--disable-extensions-except=$extensionPath",
  $url
)

Write-Host "Started browser with ProctorAI Browser Guard."
