# Detached backend launcher for Kulima OS (used by validation tooling).
$scriptRoot = Split-Path -Parent $MyInvocation.MyCommand.Path
$projectRoot = Split-Path -Parent $scriptRoot
Set-Location $projectRoot
$env:PYTHONPATH = $projectRoot
Get-Content (Join-Path $projectRoot "backend\.env") | ForEach-Object {
    if ($_ -match '^\s*([^#][^=]+)=(.*)$') {
        [System.Environment]::SetEnvironmentVariable($Matches[1].Trim(), $Matches[2].Trim().Trim('"'), "Process")
    }
}
python -m uvicorn backend.app.main:app --host 127.0.0.1 --port 8000 *> (Join-Path $projectRoot "backend_uvicorn.log")
