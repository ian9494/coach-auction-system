$ErrorActionPreference = 'Stop'
$projectRoot = Split-Path -Parent $PSScriptRoot
Push-Location -LiteralPath $projectRoot
try {
    $pythonPath = Join-Path $projectRoot '.venv\Scripts\python.exe'
    if (Test-Path -LiteralPath $pythonPath) {
        & $pythonPath -m final_project.client.coach_app
    } else {
        python -m final_project.client.coach_app
    }
    if ($LASTEXITCODE -ne 0) { throw 'Coach client startup failed.' }
} finally {
    Pop-Location
}
