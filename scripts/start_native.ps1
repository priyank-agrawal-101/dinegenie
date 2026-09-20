param(
    [ValidateSet("staging", "production")]
    [string]$Environment = "staging",
    [string]$EnvironmentFile = ""
)

$ErrorActionPreference = "Stop"
$repositoryRoot = (Resolve-Path (Join-Path $PSScriptRoot "..")).Path
if (-not $EnvironmentFile) { $EnvironmentFile = Join-Path $repositoryRoot ".env.$Environment" }
if (-not (Test-Path -LiteralPath $EnvironmentFile)) {
    throw "Missing environment file: $EnvironmentFile"
}

Get-Content -LiteralPath $EnvironmentFile | ForEach-Object {
    if ($_ -match '^\s*([^#][^=]*)=(.*)$') {
        [Environment]::SetEnvironmentVariable($matches[1].Trim(), $matches[2], "Process")
    }
}

Push-Location $repositoryRoot
try {
    & ".\.venv\Scripts\python.exe" -m uvicorn app.main:app --app-dir apps/api `
        --host $env:APP_API_HOST --port $env:APP_API_PORT --workers 1 --no-access-log
}
finally {
    Pop-Location
}
