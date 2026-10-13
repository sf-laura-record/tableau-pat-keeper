# Tableau PAT Keeper — Windows setup
# Run once from PowerShell: .\setup.ps1
# Requires Python 3.10+ from python.org (NOT the Microsoft Store version — it lacks tkinter)

$ErrorActionPreference = "Stop"
$ScriptDir = Split-Path -Parent $MyInvocation.MyCommand.Path

Write-Host "=== Tableau PAT Keeper setup ===" -ForegroundColor Cyan

# Locate python
$Python = $null
foreach ($candidate in @("python", "python3", "py")) {
    try {
        $ver = & $candidate --version 2>&1
        if ($ver -match "Python 3\.(\d+)") {
            $minor = [int]$Matches[1]
            if ($minor -ge 10) { $Python = $candidate; break }
        }
    } catch {}
}
if (-not $Python) {
    Write-Error (
        "Python 3.10+ not found.`n" +
        "Install from https://www.python.org/downloads/ (tick 'Add to PATH').`n" +
        "Use the python.org installer — NOT the Microsoft Store version (it lacks tkinter)."
    )
    exit 1
}
Write-Host "Python: $Python ($( & $Python --version 2>&1 ))"

# Install deps
Write-Host "Installing dependencies (keyring, requests)..."
& $Python -m pip install --quiet --user keyring requests

Write-Host ""
Write-Host "Done. Next steps:" -ForegroundColor Green
Write-Host "  1. Add a PAT:        python $ScriptDir\pat_keeper.py add --server <url> --site <content-url> --pat-name <name> --pat-secret <secret>"
Write-Host "  2. Open GUI:         python $ScriptDir\pat_keeper.py gui"
Write-Host "  3. Install schedule: python $ScriptDir\pat_keeper.py install-cron --days 7"
Write-Host "  4. Manual refresh:   python $ScriptDir\pat_keeper.py refresh"
Write-Host ""
Write-Host "Manifest + log stored in: $env:USERPROFILE\.tableau-pat-keeper\"
