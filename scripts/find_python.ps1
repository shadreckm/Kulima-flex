# Find Python interpreter on this machine
$found = @()
foreach ($base in @("$env:LOCALAPPDATA\Programs\Python", "C:\Program Files", "C:\")) {
    if (Test-Path $base) {
        Get-ChildItem $base -Directory -ErrorAction SilentlyContinue |
            Where-Object { $_.Name -match '^Python' } |
            ForEach-Object {
                $exe = Join-Path $_.FullName 'python.exe'
                if (Test-Path $exe) { $found += $exe }
            }
    }
}
foreach ($exe in $found) { Write-Output "FOUND: $exe" }
if (-not $found) { Write-Output "NO_PYTHON_FOUND" }
Write-Output "---commands---"
foreach ($name in @('python', 'python3', 'py')) {
    $cmd = Get-Command $name -ErrorAction SilentlyContinue
    if ($cmd) { Write-Output "$name => $($cmd.Source)" }
}
