# Tableau PAT Keeper

Keeps your Tableau Cloud Personal Access Tokens alive automatically.  
PATs expire after 15 days of inactivity. This tool signs in and out once a week to reset the timer — no manual action needed after setup.

---

## What's in this folder

| File | Purpose |
|---|---|
| `pat_keeper.py` | The tool itself — GUI + all CLI commands |
| `Install - Mac.command` | macOS double-click installer |
| `Install - Windows.ps1` | Windows installer (right-click → Run with PowerShell) |

---

## Installation

### macOS
1. Double-click **`Install - Mac.command`**
2. If macOS blocks it: right-click → **Open** → **Open anyway**
3. Terminal opens and runs the installer — it installs Python packages and sets up the weekly schedule
4. Done. Open the GUI any time with:
   ```
   python3 /path/to/pat_keeper.py gui
   ```

### Windows
1. Right-click **`Install - Windows.ps1`** → **Run with PowerShell**
2. If PowerShell blocks it, run this first in PowerShell, then try again:
   ```
   Set-ExecutionPolicy -Scope CurrentUser RemoteSigned
   ```
3. Done. Open the GUI any time with:
   ```
   python "C:\path\to\pat_keeper.py" gui
   ```

### Python requirement
- **Python 3.10 or newer** — both installers check this and tell you what to install if needed
- **macOS:** `brew install python` or https://www.python.org/downloads/
- **Windows:** https://www.python.org/downloads/ — use the python.org installer, **not** the Microsoft Store version (it's missing the GUI library)

---

## Adding your first PAT

1. Open the GUI from your terminal: `python3 pat_keeper.py gui`
2. Click **New PAT**
3. Fill in:
   - **Label** — a friendly name, e.g. `The Outpost`
   - **Server URL** — the hostname only, e.g. `https://prod-useast-a.online.tableau.com`
   - **Site URI** — the short name after `/site/` in your browser URL, e.g. `DataArcade`
   - **PAT Name** — the name you gave the PAT when you created it in Tableau Cloud
   - **PAT Secret** — the secret value (only shown once in Tableau Cloud)
4. Click **Save**
5. Click **Refresh Selected** to test it immediately — you'll see ✓ or ✗ with the error

To find your Site URI: log into Tableau Cloud and look at the URL. It's the segment after `/site/`:
```
https://prod-useast-a.online.tableau.com/#/site/DataArcade/home
                                                    ↑
                                               Site URI = DataArcade
```

---

## How PAT secrets are kept secure

- **Secrets are never written to disk** — they are stored exclusively in your OS credential vault:
  - macOS → **Keychain**
  - Windows → **Windows Credential Manager**
- The only file written to disk is `~/.tableau-pat-keeper/manifest.json`, which contains server URLs, site URIs, PAT names, labels, and last-refresh timestamps — **no secrets**
- That manifest file is safe to share or back up
- The credential vault is user-scoped — another user on the same machine cannot read your secrets

---

## Automatic refresh schedule

The installer sets up a weekly job that runs every **Tuesday at 12:00 noon** (your computer's local time):
- macOS/Linux: a crontab entry
- Windows: a Windows Scheduled Task named `TableauPATKeeper`

The job runs silently in the background. Results are logged to:
```
~/.tableau-pat-keeper/refresh.log
```

**What if my laptop is off on Tuesday?**  
The job is skipped for that week. With a 7-day refresh cadence and a 15-day expiry, you have an 8-day buffer — one missed Tuesday won't cause a PAT to expire as long as the laptop is used at least once every two weeks.

To manually trigger a refresh at any time, use the **Refresh Selected** or **Refresh All** buttons in the GUI, or run:
```
python3 pat_keeper.py refresh
```

---

## Managing the schedule

```bash
# Remove the schedule
python3 pat_keeper.py uninstall-cron

# Re-install it
python3 pat_keeper.py install-cron

# Check it's there (macOS/Linux)
crontab -l
```

---

## CLI reference

```
python3 pat_keeper.py gui                    # Open the GUI
python3 pat_keeper.py list                   # List all stored PATs (no secrets shown)
python3 pat_keeper.py refresh                # Refresh all PATs now
python3 pat_keeper.py refresh --dry-run      # Test run, no actual sign-in
python3 pat_keeper.py install-cron           # Set up weekly Tuesday noon schedule
python3 pat_keeper.py uninstall-cron         # Remove the schedule

python3 pat_keeper.py add \
  --server https://prod-useast-a.online.tableau.com \
  --site DataArcade \
  --pat-name my-pat \
  --pat-secret xxxxxxxxxxx

python3 pat_keeper.py remove --site DataArcade --pat-name my-pat
```
