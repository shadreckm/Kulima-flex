# Kulima OS — Backend startup script
# Run from the project root: .\start_backend.ps1

$scriptRoot = Split-Path -Parent $MyInvocation.MyCommand.Path
Set-Location $scriptRoot

$env:PYTHONPATH = (Get-Location).Path
Write-Host "PYTHONPATH set to: $env:PYTHONPATH"

# Load backend .env into current process
$envFile = Join-Path $scriptRoot "backend\.env"
if (-Not (Test-Path $envFile)) {
    Write-Error "Backend .env file not found at $envFile"
    exit 1
}

Get-Content $envFile | ForEach-Object {
    if ($_ -match '^\s*([^#][^=]+)=(.*)$') {
        $key   = $Matches[1].Trim()
        $value = $Matches[2].Trim().Trim('"')
        [System.Environment]::SetEnvironmentVariable($key, $value, "Process")
    }
}

Write-Host "Starting Kulima OS backend on http://127.0.0.1:8000 ..."
$pythonExe = Join-Path $scriptRoot "venv\Scripts\python.exe"
if (-Not (Test-Path $pythonExe)) {
    Write-Error "Python executable not found at $pythonExe"
    exit 1
}

& $pythonExe -m uvicorn backend.app.main:app --reload --host 127.0.0.1 --port 8000
