<#
Start the frontend on Windows with a project-local Node.js runtime.

This script pins Node.js to 18.20.4 without changing the global PATH or
system Node.js installation. The runtime is installed under ./runtime.

Usage:
  powershell -ExecutionPolicy Bypass -File scripts\start-frontend.ps1
#>

param(
  [string]$NodeVersion = "18.20.4",
  [string]$FrontendHost = "127.0.0.1",
  [int]$FrontendPort = 5173
)

$ErrorActionPreference = "Stop"

$ScriptDir = Split-Path -Parent $MyInvocation.MyCommand.Path
$RootDir = Resolve-Path (Join-Path $ScriptDir "..")
$RuntimeRoot = if ($env:RUNTIME_ROOT) { $env:RUNTIME_ROOT } else { Join-Path $RootDir "runtime" }
$RuntimeRoot = $ExecutionContext.SessionState.Path.GetUnresolvedProviderPathFromPSPath($RuntimeRoot)
$NodeDist = "node-v$NodeVersion-win-x64"
$NodeDir = Join-Path $RuntimeRoot $NodeDist
$NodeExe = Join-Path $NodeDir "node.exe"
$NpmCmd = Join-Path $NodeDir "npm.cmd"
$NodeZip = Join-Path $RuntimeRoot "$NodeDist.zip"
$FrontendDir = Join-Path $RootDir "frontend"

function Write-Log {
  param([string]$Message)
  Write-Host "[$(Get-Date -Format 'yyyy-MM-dd HH:mm:ss')] $Message"
}

function Download-File {
  param(
    [string]$Url,
    [string]$Output
  )
  Write-Log "Downloading $Url"
  Invoke-WebRequest -Uri $Url -OutFile $Output
}

function Ensure-Node {
  if (Test-Path $NodeExe) {
    return
  }

  New-Item -ItemType Directory -Force -Path $RuntimeRoot | Out-Null

  if (-not (Test-Path $NodeZip)) {
    $PrimaryUrl = "https://npmmirror.com/mirrors/node/v$NodeVersion/$NodeDist.zip"
    $FallbackUrl = "https://nodejs.org/dist/v$NodeVersion/$NodeDist.zip"
    try {
      Download-File -Url $PrimaryUrl -Output $NodeZip
    }
    catch {
      Write-Log "Primary download failed, trying official Node.js mirror"
      if (Test-Path $NodeZip) {
        Remove-Item -Force $NodeZip
      }
      Download-File -Url $FallbackUrl -Output $NodeZip
    }
  }
  else {
    Write-Log "Using local Node.js archive: $NodeZip"
  }

  if (Test-Path $NodeDir) {
    Remove-Item -Recurse -Force $NodeDir
  }
  Write-Log "Extracting Node.js $NodeVersion to $RuntimeRoot"
  Expand-Archive -Force -Path $NodeZip -DestinationPath $RuntimeRoot
}

Ensure-Node

$ActualNodeVersion = & $NodeExe -p "process.versions.node"
if ($ActualNodeVersion -ne $NodeVersion) {
  throw "Expected Node.js $NodeVersion at $NodeExe, got $ActualNodeVersion"
}

# Scope the pinned Node.js to this process only. This does not modify global PATH.
$env:Path = "$NodeDir;$env:Path"
$env:ELECTRON_SKIP_BINARY_DOWNLOAD = "1"

Write-Log "Using Node.js: $(& $NodeExe -v) ($NodeExe)"
Write-Log "Using npm: $(& $NpmCmd -v) ($NpmCmd)"

$ViteCmd = Join-Path $FrontendDir "node_modules\.bin\vite.cmd"
if (-not (Test-Path $ViteCmd)) {
  Write-Log "Frontend dependencies missing, installing with project-local Node.js"
  if (Test-Path (Join-Path $FrontendDir "package-lock.json")) {
    & $NpmCmd --prefix $FrontendDir ci
  }
  else {
    & $NpmCmd --prefix $FrontendDir install
  }
  if ($LASTEXITCODE -ne 0) {
    throw "npm dependency installation failed with exit code $LASTEXITCODE"
  }
}

Write-Log "Starting frontend on http://$FrontendHost`:$FrontendPort"
& $NpmCmd --prefix $FrontendDir run dev -- --host $FrontendHost --port $FrontendPort
