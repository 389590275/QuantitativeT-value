<#
Create a CentOS deployment package from Windows.

Usage:
  powershell -ExecutionPolicy Bypass -File scripts\package.ps1
  powershell -ExecutionPolicy Bypass -File scripts\package.ps1 -PackagePath C:\tmp\t0-quant-assistant.tar.gz
#>

param(
  [string]$PackagePath = ""
)

$ErrorActionPreference = "Stop"

$ScriptDir = Split-Path -Parent $MyInvocation.MyCommand.Path
$RootDir = Resolve-Path (Join-Path $ScriptDir "..")
$PackageDir = if ($env:PACKAGE_DIR) { $env:PACKAGE_DIR } else { Join-Path $RootDir "dist-package" }
$PackageDir = $ExecutionContext.SessionState.Path.GetUnresolvedProviderPathFromPSPath($PackageDir)

if ([string]::IsNullOrWhiteSpace($PackagePath)) {
  $Timestamp = Get-Date -Format "yyyyMMdd-HHmmss"
  $PackagePath = Join-Path $PackageDir "t0-quant-assistant-$Timestamp.tar.gz"
}

$PackagePath = $ExecutionContext.SessionState.Path.GetUnresolvedProviderPathFromPSPath($PackagePath)
$PackageParent = Split-Path -Parent $PackagePath

if (Test-Path $PackageDir) {
  Write-Host "[$(Get-Date -Format 'yyyy-MM-dd HH:mm:ss')] Removing package directory: $PackageDir"
  Remove-Item -Recurse -Force -Path $PackageDir
}

New-Item -ItemType Directory -Force -Path $PackageParent | Out-Null

if (-not (Get-Command tar.exe -ErrorAction SilentlyContinue)) {
  throw "tar.exe not found. Windows 10 should include it; otherwise install Git for Windows or enable bsdtar."
}

Write-Host "[$(Get-Date -Format 'yyyy-MM-dd HH:mm:ss')] Packaging $RootDir"

$excludeArgs = @(
  "--exclude=./.git",
  "--exclude=./data",
  "--exclude=./logs",
  "--exclude=./run",
  "--exclude=./runtime",
  "--exclude=./venv",
  "--exclude=./.venv",
  "--exclude=./backend/__pycache__",
  "--exclude=./backend/app/**/__pycache__",
  "--exclude=./frontend/node_modules",
  "--exclude=./frontend/dist",
  "--exclude=./frontend/dist-electron",
  "--exclude=./frontend/release",
  "--exclude=./dist-package/*.tar.gz"
)

Push-Location $RootDir
try {
  & tar.exe -czf $PackagePath @excludeArgs .
  if ($LASTEXITCODE -ne 0) {
    throw "tar.exe failed with exit code $LASTEXITCODE"
  }
}
finally {
  Pop-Location
}

Write-Host "[$(Get-Date -Format 'yyyy-MM-dd HH:mm:ss')] Package created: $PackagePath"
Write-Host "Upload it to CentOS, then extract or deploy it under /data/app."
