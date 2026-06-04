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
$ProdEnvPath = Join-Path $RootDir ".env.prod"

if (Test-Path $PackageDir) {
  Write-Host "[$(Get-Date -Format 'yyyy-MM-dd HH:mm:ss')] Removing package directory: $PackageDir"
  Remove-Item -Recurse -Force -Path $PackageDir
}

New-Item -ItemType Directory -Force -Path $PackageParent | Out-Null

if (-not (Test-Path $ProdEnvPath)) {
  throw ".env.prod not found: $ProdEnvPath"
}

if (-not (Get-Command tar.exe -ErrorAction SilentlyContinue)) {
  throw "tar.exe not found. Windows 10 should include it; otherwise install Git for Windows or enable bsdtar."
}

if (-not (Get-Command robocopy.exe -ErrorAction SilentlyContinue)) {
  throw "robocopy.exe not found. Windows should include it."
}

Write-Host "[$(Get-Date -Format 'yyyy-MM-dd HH:mm:ss')] Packaging $RootDir"

$StageDir = Join-Path ([System.IO.Path]::GetTempPath()) "t0-quant-package-stage-$PID-$(Get-Date -Format 'yyyyMMddHHmmssfff')"
New-Item -ItemType Directory -Force -Path $StageDir | Out-Null

$excludeDirs = @(
  ".git",
  "data",
  "logs",
  "run",
  "runtime",
  "venv",
  ".venv",
  "__pycache__",
  "node_modules",
  "dist",
  "dist-electron",
  "release",
  "dist-package"
)
$excludeFiles = @(
  ".env",
  ".env.prod",
  "*.pyc"
)

& robocopy.exe $RootDir $StageDir /E /XD @excludeDirs /XF @excludeFiles /NFL /NDL /NJH /NJS /NP | Out-Null
if ($LASTEXITCODE -gt 7) {
  throw "robocopy.exe failed with exit code $LASTEXITCODE"
}

Copy-Item -Force -Path $ProdEnvPath -Destination (Join-Path $StageDir ".env")

Push-Location $StageDir
try {
  & tar.exe -czf $PackagePath .
  if ($LASTEXITCODE -ne 0) {
    throw "tar.exe failed with exit code $LASTEXITCODE"
  }
}
finally {
  Pop-Location
  if (Test-Path $StageDir) {
    Remove-Item -Recurse -Force -Path $StageDir
  }
}

Write-Host "[$(Get-Date -Format 'yyyy-MM-dd HH:mm:ss')] Package created: $PackagePath"
Write-Host "Upload it to CentOS, then extract or deploy it under /data/app."
Write-Host "Production data (SQLite): /data/save/t0.db (set via DB_PATH in packaged .env)."
Write-Host "After deploy, run: bash /data/app/scripts/init_prod_dirs.sh"
