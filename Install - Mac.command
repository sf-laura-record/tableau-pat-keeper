#!/usr/bin/env bash
# Tableau PAT Keeper — macOS installer
# Double-click this file in Finder to install.
# If macOS blocks it: right-click → Open → Open anyway.

set -euo pipefail
SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"

echo "========================================"
echo "  Tableau PAT Keeper — macOS Installer"
echo "========================================"
echo ""

# ── Python check ─────────────────────────────────────────────────────────────
PYTHON=$(command -v python3 || true)
if [[ -z "$PYTHON" ]]; then
  echo "ERROR: Python not found."
  echo ""
  echo "Install it with Homebrew:   brew install python"
  echo "Or download from:           https://www.python.org/downloads/"
  echo ""
  read -rp "Press Enter to close..."
  exit 1
fi

PY_MAJOR=$("$PYTHON" -c "import sys; print(sys.version_info.major)")
PY_MINOR=$("$PYTHON" -c "import sys; print(sys.version_info.minor)")
PY_VER="$PY_MAJOR.$PY_MINOR"

if [[ "$PY_MAJOR" -lt 3 ]] || [[ "$PY_MAJOR" -eq 3 && "$PY_MINOR" -lt 10 ]]; then
  echo "ERROR: Python 3.10 or newer required (you have $PY_VER)."
  echo ""
  echo "Install a newer version:    brew install python"
  echo "Or download from:           https://www.python.org/downloads/"
  echo ""
  read -rp "Press Enter to close..."
  exit 1
fi

echo "Python $PY_VER — OK"
echo ""

# ── Install Python deps ───────────────────────────────────────────────────────
echo "Installing required packages (keyring, requests)..."
"$PYTHON" -m pip install --quiet --user keyring requests
echo "Packages installed."
echo ""

# ── Make script executable ────────────────────────────────────────────────────
chmod +x "$SCRIPT_DIR/pat_keeper.py"

# ── Schedule weekly refresh ───────────────────────────────────────────────────
echo "Setting up weekly auto-refresh (every Tuesday at noon)..."
"$PYTHON" "$SCRIPT_DIR/pat_keeper.py" install-cron
echo ""

echo "========================================"
echo "  Installation complete!"
echo ""
echo "  To open the PAT manager:"
echo "  python3 \"$SCRIPT_DIR/pat_keeper.py\" gui"
echo ""
echo "  Your PAT secrets are stored in macOS"
echo "  Keychain — never written to disk."
echo "========================================"
echo ""
read -rp "Press Enter to close..."
