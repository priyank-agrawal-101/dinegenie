param([string]$Python = "python")

$ErrorActionPreference = "Stop"
$repositoryRoot = (Resolve-Path (Join-Path $PSScriptRoot "..")).Path
Push-Location $repositoryRoot
try {
    & $Python -m venv .venv
    if ($LASTEXITCODE -ne 0) { throw "Virtual environment creation failed" }
    & ".\.venv\Scripts\python.exe" -m pip install --requirement requirements.lock
    if ($LASTEXITCODE -ne 0) { throw "Locked dependency installation failed" }
}
finally {
    Pop-Location
}
