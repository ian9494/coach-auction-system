param(
    [string]$DemoRoot,
    [string]$Config
)
$ErrorActionPreference = 'Stop'
$projectRoot = Split-Path -Parent $PSScriptRoot
# Resolve user paths before changing the caller's working directory.
$launchArgs = @('-m', 'final_project.server.app')
if ($DemoRoot) { $launchArgs += @('--demo-root', (Resolve-Path -LiteralPath $DemoRoot).Path) }
if ($Config) { $launchArgs += @('--config', (Resolve-Path -LiteralPath $Config).Path) }
Push-Location -LiteralPath $projectRoot
try {
    $pythonPath = Join-Path $projectRoot '.venv\Scripts\python.exe'
    if (Test-Path -LiteralPath $pythonPath) { & $pythonPath @launchArgs }
    else { python @launchArgs }
    if ($LASTEXITCODE -ne 0) { throw 'Final project server startup failed.' }
} finally { Pop-Location }
