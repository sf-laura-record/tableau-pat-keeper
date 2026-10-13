# Tableau PAT Keeper — Windows installer
# Right-click this file → "Run with PowerShell"
# Requires Python 3.10+ from python.org (NOT the Microsoft Store version)

$ErrorActionPreference = "Stop"
$ScriptDir = Split-Path -Parent $MyInvocation.MyCommand.Path

Write-Host "========================================" -ForegroundColor Cyan
Write-Host "  Tableau PAT Keeper - Windows Installer"
Write-Host "========================================`n"

# ── Python check ──────────────────────────────────────────────────────────────
$Python = $null
foreach ($candidate in @("python", "python3", "py")) {
    try {
        $ver = & $candidate --version 2>&1
        if ($ver -match "Python 3\.(\d+)") {
            if ([int]$Matches[1] -ge 10) { $Python = $candidate; break }
        }
    } catch {}
}

if (-not $Python) {
    Write-Host "ERROR: Python 3.10 or newer not found.`n" -ForegroundColor Red
    Write-Host "Download from: https://www.python.org/downloads/"
    Write-Host "  - Tick 'Add Python to PATH' during install"
    Write-Host "  - Use the python.org installer, NOT the Microsoft Store version`n"
    Read-Host "Press Enter to close"
    exit 1
}

$pyVer = & $Python --version 2>&1
Write-Host "$pyVer - OK`n" -ForegroundColor Green

# ── Install Python deps ───────────────────────────────────────────────────────
Write-Host "Installing required packages (keyring, requests)..."
& $Python -m pip install --quiet --user keyring requests
Write-Host "Packages installed.`n"

# ── Schedule weekly refresh ───────────────────────────────────────────────────
Write-Host "Setting up weekly auto-refresh (every Tuesday at noon)..."
& $Python "$ScriptDir\pat_keeper.py" install-cron
Write-Host ""

Write-Host "========================================" -ForegroundColor Green
Write-Host "  Installation complete!"
Write-Host ""
Write-Host "  To open the PAT manager, run:"
Write-Host "  python `"$ScriptDir\pat_keeper.py`" gui"
Write-Host ""
Write-Host "  Your PAT secrets are stored in Windows"
Write-Host "  Credential Manager - never written to disk."
Write-Host "========================================`n"
Read-Host "Press Enter to close"
