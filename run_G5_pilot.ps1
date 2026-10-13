param(
    [Parameter(Mandatory=$true)][string]$InputTiff,
    [Parameter(Mandatory=$true)][string]$OutputDirectory,
    [ValidateSet('studio','native-exploratory')][string]$Profile='native-exploratory',
    [string]$WeightsDirectory='work/models',
    [string]$Assets='studio_assets.json',
    [string]$Planes='1',
    [string]$Device='auto',
    [string]$Python=(Join-Path $PSScriptRoot '.venv\Scripts\python.exe')
)
$ErrorActionPreference='Stop'
& $Python -m ultra.studio run --input $InputTiff --out $OutputDirectory --profile $Profile --weights $WeightsDirectory --assets $Assets --planes $Planes --device $Device
if ($LASTEXITCODE -ne 0) { throw 'ULTRA run failed. Read the error above and workflow.json.' }
Write-Host "Results: $OutputDirectory"
