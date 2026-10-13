$ErrorActionPreference = 'Stop'
$projectRoot = $PSScriptRoot
$localPython = Join-Path (Split-Path $projectRoot -Parent) '.venv\Scripts\python.exe'
if (-not (Test-Path -LiteralPath $localPython)) {
    Write-Error 'Python environment missing. See README installation instructions.'
    exit 1
}
Set-Location -LiteralPath (Split-Path $projectRoot -Parent)
& $localPython -m ultra.studio gui
