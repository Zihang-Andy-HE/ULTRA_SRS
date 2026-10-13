param([ValidateSet('studio','native-exploratory')][string]$Profile='native-exploratory')
$ErrorActionPreference='Stop'
$workRoot=Split-Path $PSScriptRoot -Parent
$pythonExe=Join-Path $workRoot '.venv\Scripts\python.exe'
$runStamp=Get-Date -Format 'yyyyMMdd_HHmmss'
$resultPath=Join-Path $workRoot ('results\pilot_'+$Profile+'_'+$runStamp)
& $pythonExe -m ultra.studio run --input (Join-Path $workRoot 'G5.tif') --out $resultPath --profile $Profile --weights (Join-Path $workRoot 'weights_srs') --assets (Join-Path $workRoot 'studio_assets.json') --planes '1,75,150' --device auto
if ($LASTEXITCODE -ne 0) { throw 'ULTRA run failed. Read the error above and workflow.json.' }
Write-Host "Results: $resultPath"
