$ErrorActionPreference = 'Stop'
$projectRoot = Split-Path -Parent $PSScriptRoot
Push-Location -LiteralPath $projectRoot
try {
    $pythonPath = Join-Path $projectRoot '.venv\Scripts\python.exe'
    if (Test-Path -LiteralPath $pythonPath) {
        & $pythonPath -m final_project.client.admin_app
    } else {
        python -m final_project.client.admin_app
    }
    if ($LASTEXITCODE -ne 0) { throw 'Admin client startup failed.' }
} finally {
    Pop-Location
}
