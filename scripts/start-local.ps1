# Run from any directory. All work is confined to this project.
$projectRoot = Split-Path -Parent $PSScriptRoot
Set-Location -LiteralPath $projectRoot
$pythonPath = Join-Path $projectRoot '.venv\Scripts\python.exe'
if (-not (Test-Path -LiteralPath $pythonPath)) {
    throw 'Create the project .venv and install requirements.lock.txt first; see README.md.'
}
if (-not (Test-Path -LiteralPath (Join-Path $projectRoot 'frontend\dist\index.html'))) {
    throw 'Build the dashboard first: cd frontend; npm ci; npm run build. See README.md.'
}
Write-Host 'Lumen is available at http://127.0.0.1:8000. Press Ctrl+C to stop.'
& $pythonPath -m uvicorn backend.app.main:app --host 127.0.0.1 --port 8000 --no-proxy-headers
