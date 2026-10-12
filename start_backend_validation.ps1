# Start backend without --reload (for validation runs).
$scriptRoot = Split-Path -Parent $MyInvocation.MyCommand.Path
Set-Location $scriptRoot
$env:PYTHONPATH = (Get-Location).Path
$envFile = Join-Path $scriptRoot "backend\.env"
Get-Content $envFile | ForEach-Object {
    if ($_ -match '^\s*([^#][^=]+)=(.*)$') {
        [System.Environment]::SetEnvironmentVariable($Matches[1].Trim(), $Matches[2].Trim().Trim('"'), "Process")
    }
}
$frontendEnvFile = Join-Path $scriptRoot "frontend\.env.local"
if (Test-Path $frontendEnvFile) {
    $line = Get-Content $frontendEnvFile | Where-Object { $_ -match '^\s*NEXTAUTH_SECRET\s*=' } | Select-Object -First 1
    if ($line -match '^\s*NEXTAUTH_SECRET\s*=(.*)$') {
        $env:NEXTAUTH_SECRET = $Matches[1].Trim().Trim('"').Trim("'")
    }
}
Write-Host "Starting Kulima backend (no reload) on http://127.0.0.1:8000 ..."
python -m uvicorn backend.app.main:app --host 127.0.0.1 --port 8000
