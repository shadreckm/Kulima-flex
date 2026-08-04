# Kulima OS — Frontend startup script
# Run from the project root: .\start_frontend.ps1

Write-Host "Starting Kulima OS frontend on http://localhost:3001 ..."
Set-Location frontend
npm run dev
