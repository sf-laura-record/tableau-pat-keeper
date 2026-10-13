#!/usr/bin/env bash
# One-shot setup for Tableau PAT Keeper
# Run once: bash setup.sh

set -euo pipefail
SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"

echo "=== Tableau PAT Keeper setup ==="

# Check Python 3.10+
PYTHON=$(command -v python3 || true)
if [[ -z "$PYTHON" ]]; then
  echo "ERROR: python3 not found."
  echo "  macOS:       brew install python"
  echo "  Linux/other: https://www.python.org/downloads/"
  exit 1
fi
PY_VER=$("$PYTHON" -c "import sys; print(f'{sys.version_info.major}.{sys.version_info.minor}')")
PY_MINOR=$("$PYTHON" -c "import sys; print(sys.version_info.minor)")
PY_MAJOR=$("$PYTHON" -c "import sys; print(sys.version_info.major)")
if [[ "$PY_MAJOR" -lt 3 ]] || [[ "$PY_MAJOR" -eq 3 && "$PY_MINOR" -lt 10 ]]; then
  echo "ERROR: Python 3.10+ required (found $PY_VER)."
  echo "  macOS:  brew install python"
  echo "  Other:  https://www.python.org/downloads/"
  exit 1
fi
echo "Python: $PYTHON ($PY_VER)"

# Install deps
echo "Installing dependencies (keyring, requests)..."
"$PYTHON" -m pip install --quiet --user keyring requests

# Make script executable
chmod +x "$SCRIPT_DIR/pat_keeper.py"

# Symlink into ~/bin if it's on PATH (best-effort)
BIN_DIR="$HOME/bin"
if [[ ":$PATH:" == *":$BIN_DIR:"* ]]; then
  mkdir -p "$BIN_DIR"
  ln -sf "$SCRIPT_DIR/pat_keeper.py" "$BIN_DIR/pat_keeper"
  echo "Symlinked: pat_keeper → $BIN_DIR/pat_keeper"
else
  echo "Note: $BIN_DIR not on PATH — run the script as: python3 $SCRIPT_DIR/pat_keeper.py"
fi

echo ""
echo "Done. Next steps:"
echo "  1. Open GUI:         python3 $SCRIPT_DIR/pat_keeper.py gui"
echo "  2. Install schedule: python3 $SCRIPT_DIR/pat_keeper.py install-cron"
echo "  3. Manual refresh:   python3 $SCRIPT_DIR/pat_keeper.py refresh"
echo ""
echo "Manifest + log stored in: $HOME/.tableau-pat-keeper/"
