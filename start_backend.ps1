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

# The frontend session and backend bearer JWT must use the same secret.
# In local development, the frontend's .env.local is the canonical source.
$frontendEnvFile = Join-Path $scriptRoot "frontend\.env.local"
if (Test-Path $frontendEnvFile) {
    $frontendSecretLine = Get-Content $frontendEnvFile | Where-Object { $_ -match '^\s*NEXTAUTH_SECRET\s*=' } | Select-Object -First 1
    if ($frontendSecretLine -match '^\s*NEXTAUTH_SECRET\s*=(.*)$') {
        $frontendSecret = $Matches[1].Trim().Trim('"').Trim("'")
        if ($frontendSecret) {
            if ($env:NEXTAUTH_SECRET -and $env:NEXTAUTH_SECRET -ne $frontendSecret) {
                Write-Warning "Backend .env NEXTAUTH_SECRET differs from frontend/.env.local; using the frontend value for this local process."
            }
            $env:NEXTAUTH_SECRET = $frontendSecret
            Write-Host "Using the local frontend NEXTAUTH_SECRET for backend JWT verification."
        }
    }
}

Write-Host "Starting Kulima OS backend on http://127.0.0.1:8000 ..."
$pythonExe = Join-Path $scriptRoot "venv\Scripts\python.exe"
if (Test-Path $pythonExe) {
    & $pythonExe -m uvicorn backend.app.main:app --reload --host 127.0.0.1 --port 8000
} else {
    $pythonCommand = Get-Command python -ErrorAction SilentlyContinue
    if (-Not $pythonCommand) {
        Write-Error "Python executable not found at $pythonExe and no system python command is available."
        exit 1
    }
    Write-Warning "Project virtualenv not found; using system Python at $($pythonCommand.Source)."
    & python -m uvicorn backend.app.main:app --reload --host 127.0.0.1 --port 8000
}
