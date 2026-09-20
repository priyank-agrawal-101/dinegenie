param(
    [string]$Version = "0.1.0-rc1",
    [string]$OutputRoot = "release"
)

$ErrorActionPreference = "Stop"
$repositoryRoot = (Resolve-Path (Join-Path $PSScriptRoot "..")).Path
if ($Version -notmatch '^[0-9A-Za-z][0-9A-Za-z._-]*$') { throw "Invalid release version" }
$releaseRoot = [IO.Path]::GetFullPath((Join-Path $repositoryRoot $OutputRoot))
if (-not $releaseRoot.StartsWith($repositoryRoot + [IO.Path]::DirectorySeparatorChar)) {
    throw "OutputRoot must be inside the repository"
}
$artifactRoot = Join-Path $releaseRoot "dinegenie-$Version"
$archive = Join-Path $releaseRoot "dinegenie-$Version.zip"

Push-Location $repositoryRoot
try {
    & ".\.venv\Scripts\ruff.exe" check apps/api pipelines scripts
    if ($LASTEXITCODE -ne 0) { throw "Ruff lint failed" }
    & ".\.venv\Scripts\ruff.exe" format --check apps/api pipelines scripts
    if ($LASTEXITCODE -ne 0) { throw "Ruff format check failed" }
    & ".\.venv\Scripts\mypy.exe" apps/api pipelines scripts
    if ($LASTEXITCODE -ne 0) { throw "Mypy failed" }
    & ".\.venv\Scripts\pytest.exe" -q --basetemp runtime-data/release-tests
    if ($LASTEXITCODE -ne 0) { throw "Pytest failed" }
    Push-Location "apps/web"
    try {
        & npm.cmd run check
        if ($LASTEXITCODE -ne 0) { throw "Web checks failed" }
    }
    finally { Pop-Location }

    if (Test-Path -LiteralPath $artifactRoot) {
        throw "Release directory already exists: $artifactRoot"
    }
    New-Item -ItemType Directory -Path $artifactRoot | Out-Null
    New-Item -ItemType Directory -Path (Join-Path $artifactRoot "apps\web") -Force | Out-Null
    Copy-Item -Recurse apps/api -Destination (Join-Path $artifactRoot "apps")
    Copy-Item -Recurse apps/web/dist -Destination (Join-Path $artifactRoot "apps\web")
    Copy-Item -Recurse pipelines,migrations,ops,scripts,docs -Destination $artifactRoot
    Remove-Item -LiteralPath (Join-Path $artifactRoot "apps\api\tests") -Recurse -Force
    Remove-Item -LiteralPath (Join-Path $artifactRoot "apps\api\Dockerfile") -Force
    Get-ChildItem -LiteralPath $artifactRoot -Directory -Recurse -Filter "__pycache__" |
        Remove-Item -Recurse -Force
    Copy-Item README.md,requirements.lock,.env.production.example -Destination $artifactRoot
    [ordered]@{
        application_version = $Version
        built_at = [DateTime]::UtcNow.ToString("o")
        migrations = @(Get-ChildItem migrations -File -Filter "*.sql" | Sort-Object Name | ForEach-Object Name)
        prompt_version = "restaurant-grounded-v1"
        response_schema_version = "ranked-evidence-v1"
        dataset_version = "record-at-deployment"
        model = "APP_LLM_MODEL-at-deployment"
    } | ConvertTo-Json -Depth 3 | Set-Content -Encoding utf8 (Join-Path $artifactRoot "release-manifest.json")
    $hashes = Get-ChildItem -File -Recurse $artifactRoot | Get-FileHash -Algorithm SHA256
    $hashes | ForEach-Object { "{0}  {1}" -f $_.Hash.ToLowerInvariant(), $_.Path.Substring($artifactRoot.Length + 1) } |
        Set-Content -Encoding utf8 (Join-Path $artifactRoot "SHA256SUMS")
    Compress-Archive -LiteralPath $artifactRoot -DestinationPath $archive
    Get-FileHash -Algorithm SHA256 $archive
}
finally {
    Pop-Location
}
