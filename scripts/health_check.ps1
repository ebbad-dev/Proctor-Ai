param(
    [string]$ApiBase = "http://127.0.0.1:5051",
    [string]$FrontendBase = "http://127.0.0.1:8080",
    [string]$VideoBase = "http://127.0.0.1:5050",
    [int]$TimeoutSec = 8
)

$ErrorActionPreference = "Stop"

function Test-Endpoint {
    param(
        [string]$Name,
        [string]$Url,
        [string]$Method = "GET",
        [int[]]$ExpectedStatus = @(200)
    )

    $result = [ordered]@{
        name = $Name
        url = $Url
        ok = $false
        status = $null
        error = $null
    }

    try {
        $response = Invoke-WebRequest -Uri $Url -Method $Method -TimeoutSec $TimeoutSec -UseBasicParsing
        $result.status = [int]$response.StatusCode
        $result.ok = $ExpectedStatus -contains $result.status
    }
    catch {
        if ($_.Exception.Response) {
            $result.status = [int]$_.Exception.Response.StatusCode
        }
        $result.error = $_.Exception.Message
    }

    [pscustomobject]$result
}

$checks = @()
$checks += Test-Endpoint -Name "fastapi_health" -Url "$ApiBase/health"
$checks += Test-Endpoint -Name "proctor_status" -Url "$ApiBase/proctor/status"
$checks += Test-Endpoint -Name "video_ping" -Url "$VideoBase/ping"
$checks += Test-Endpoint -Name "frontend_login" -Url "$FrontendBase/login"

$checks | Format-Table -AutoSize

$failed = $checks | Where-Object { -not $_.ok }
if ($failed) {
    Write-Error ("Health check failed: " + (($failed | ForEach-Object { $_.name }) -join ", "))
    exit 1
}

Write-Host "ProctorAI health check passed."
