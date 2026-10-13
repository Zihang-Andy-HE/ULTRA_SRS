param([string]$Python = (Join-Path $PSScriptRoot '.venv\Scripts\python.exe'))
$ErrorActionPreference = 'Stop'
if (-not (Test-Path -LiteralPath $Python)) {
    throw 'Python environment missing. Create .venv in the repository or pass -Python with an interpreter path.'
}
& $Python -m ultra.studio gui
if ($LASTEXITCODE -ne 0) { throw 'ULTRA Studio exited with an error.' }
