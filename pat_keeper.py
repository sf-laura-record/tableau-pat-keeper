#!/usr/bin/env python3
"""
Tableau PAT Keeper
- Stores PAT secrets in macOS Keychain (keyring) + plain manifest for listing
- Refreshes PATs by signing in and out via Tableau REST API
- GUI modal for adding/editing/removing entries (falls back to CLI)
- Designed to run from cron / Task Scheduler every ~7 days
- Requires Python 3.10+  (str | None union syntax)
"""
import sys

# ── Version gate — must run before any other import ──────────────────────────
if sys.version_info < (3, 10):
    print(
        f"ERROR: Python 3.10 or newer required (you have {sys.version.split()[0]}).\n"
        "  macOS/Linux: brew install python  OR  https://www.python.org/downloads/\n"
        "  Windows:     https://www.python.org/downloads/  (tick 'Add to PATH')\n"
        "               Use the python.org installer, NOT the Microsoft Store version."
    )
    sys.exit(1)

# ── Dependency check — offer to install if missing ───────────────────────────
def _ensure_deps():
    missing = []
    for pkg in ("keyring", "requests"):
        try:
            __import__(pkg)
        except ImportError:
            missing.append(pkg)
    if not missing:
        return
    print(f"Missing packages: {', '.join(missing)}")
    answer = input("Install them now with pip? [Y/n]: ").strip().lower()
    if answer in ("", "y", "yes"):
        import subprocess
        subprocess.check_call([sys.executable, "-m", "pip", "install", "--user"] + missing)
        print("Installed. Restarting...")
        os.execv(sys.executable, [sys.executable] + sys.argv)
    else:
        print("Cannot continue without required packages.")
        sys.exit(1)

import os  # needed by _ensure_deps restart
_ensure_deps()

import json
import argparse
import requests
from pathlib import Path

try:
    import keyring
    KEYRING_AVAILABLE = True
except ImportError:
    KEYRING_AVAILABLE = False

MANIFEST_PATH = Path(os.environ.get("PAT_KEEPER_MANIFEST", Path.home() / ".tableau-pat-keeper" / "manifest.json"))
KEYRING_SERVICE = "tableau-pat-keeper"
LOG_PATH = MANIFEST_PATH.parent / "refresh.log"
TABLEAU_API_VERSION = "3.24"


# ── Manifest helpers ─────────────────────────────────────────────────────────

def load_manifest() -> list[dict]:
    if not MANIFEST_PATH.exists():
        return []
    with open(MANIFEST_PATH) as f:
        return json.load(f)


def save_manifest(entries: list[dict]):
    MANIFEST_PATH.parent.mkdir(parents=True, exist_ok=True)
    with open(MANIFEST_PATH, "w") as f:
        json.dump(entries, f, indent=2)


def manifest_key(site_url: str, pat_name: str) -> str:
    return f"{site_url}|{pat_name}"


def entry_exists(entries: list[dict], site_url: str, pat_name: str) -> bool:
    return any(e["site_url"] == site_url and e["pat_name"] == pat_name for e in entries)


# ── Keyring helpers ──────────────────────────────────────────────────────────

def store_secret(site_url: str, pat_name: str, pat_secret: str):
    if not KEYRING_AVAILABLE:
        raise RuntimeError("keyring package not installed — run: pip install keyring")
    keyring.set_password(KEYRING_SERVICE, manifest_key(site_url, pat_name), pat_secret)


def get_secret(site_url: str, pat_name: str) -> "str | None":
    if not KEYRING_AVAILABLE:
        raise RuntimeError("keyring package not installed — run: pip install keyring")
    return keyring.get_password(KEYRING_SERVICE, manifest_key(site_url, pat_name))


def delete_secret(site_url: str, pat_name: str):
    if not KEYRING_AVAILABLE:
        return
    try:
        keyring.delete_password(KEYRING_SERVICE, manifest_key(site_url, pat_name))
    except keyring.errors.PasswordDeleteError:
        pass


# ── REST API: sign in / sign out ─────────────────────────────────────────────

def refresh_pat(site_url: str, pat_name: str, pat_secret: str, server_url: str) -> tuple[bool, str]:
    """Sign in then immediately sign out to reset the 15-day expiry clock."""
    signin_url = f"{server_url}/api/{TABLEAU_API_VERSION}/auth/signin"
    headers = {"Content-Type": "application/json", "Accept": "application/json"}
    payload = {
        "credentials": {
            "personalAccessTokenName": pat_name,
            "personalAccessTokenSecret": pat_secret,
            "site": {"contentUrl": site_url},
        }
    }
    try:
        r = requests.post(signin_url, json=payload, headers=headers, timeout=30)
        if r.status_code != 200:
            return False, f"sign-in HTTP {r.status_code}: {r.text[:200]}"
        token = r.json()["credentials"]["token"]

        signout_url = f"{server_url}/api/{TABLEAU_API_VERSION}/auth/signout"
        requests.post(signout_url, headers={**headers, "X-Tableau-Auth": token}, timeout=15)
        return True, "ok"
    except Exception as exc:
        return False, str(exc)


# ── Log helper ───────────────────────────────────────────────────────────────

def log(msg: str):
    from datetime import datetime
    LOG_PATH.parent.mkdir(parents=True, exist_ok=True)
    line = f"{datetime.now().isoformat()} {msg}"
    print(line)
    with open(LOG_PATH, "a") as f:
        f.write(line + "\n")


def fmt_refresh(iso: "str | None") -> str:
    if not iso:
        return "never"
    from datetime import datetime
    try:
        return datetime.fromisoformat(iso).strftime("%-d %b %Y  %-I:%M %p")
    except ValueError:
        return iso


# ── CLI commands ─────────────────────────────────────────────────────────────

def cmd_list():
    entries = load_manifest()
    if not entries:
        print("No PATs stored.")
        return
    print(f"{'#':<4} {'Server':<42} {'Site URL':<24} {'PAT Name':<28} Last refreshed")
    print("-" * 120)
    for i, e in enumerate(entries, 1):
        print(f"{i:<4} {e['server_url']:<42} {e['site_url']:<24} {e['pat_name']:<28} {fmt_refresh(e.get('last_refresh'))}")


def cmd_add(server_url: str, site_url: str, pat_name: str, pat_secret: str, label: str = ""):
    entries = load_manifest()
    if entry_exists(entries, site_url, pat_name):
        print(f"Entry already exists for {site_url} / {pat_name}. Use 'update' to change it.")
        return
    store_secret(site_url, pat_name, pat_secret)
    entries.append({
        "server_url": server_url.rstrip("/"),
        "site_url": site_url,
        "pat_name": pat_name,
        "label": label or f"{site_url} / {pat_name}",
        "last_refresh": None,
    })
    save_manifest(entries)
    print(f"Added: {site_url} / {pat_name}")


def cmd_update(server_url: str, site_url: str, pat_name: str, pat_secret: str):
    entries = load_manifest()
    if not entry_exists(entries, site_url, pat_name):
        print(f"No entry found for {site_url} / {pat_name}. Use 'add' first.")
        return
    store_secret(site_url, pat_name, pat_secret)
    print(f"Secret updated for {site_url} / {pat_name}")


def cmd_remove(site_url: str, pat_name: str):
    entries = load_manifest()
    before = len(entries)
    entries = [e for e in entries if not (e["site_url"] == site_url and e["pat_name"] == pat_name)]
    if len(entries) == before:
        print(f"No entry found for {site_url} / {pat_name}.")
        return
    delete_secret(site_url, pat_name)
    save_manifest(entries)
    print(f"Removed: {site_url} / {pat_name}")


def cmd_refresh(dry_run: bool = False) -> list[dict]:
    """Refresh all PATs. Returns list of {label, ok, msg} for each entry."""
    from datetime import datetime
    entries = load_manifest()
    results = []
    if not entries:
        log("No PATs configured.")
        return results
    changed = False
    for e in entries:
        label = e.get("label") or f"{e['site_url']} / {e['pat_name']}"
        secret = get_secret(e["site_url"], e["pat_name"])
        if not secret:
            msg = "no secret found in keychain"
            log(f"WARN  {label}: {msg}")
            results.append({"label": label, "ok": False, "msg": msg})
            continue
        if dry_run:
            log(f"DRY   would refresh {label}")
            results.append({"label": label, "ok": True, "msg": "dry run"})
            continue
        ok, msg = refresh_pat(e["site_url"], e["pat_name"], secret, e["server_url"])
        status = "OK   " if ok else "FAIL "
        log(f"{status} {label}: {msg}")
        results.append({"label": label, "ok": ok, "msg": msg})
        if ok:
            e["last_refresh"] = datetime.now().isoformat()
            changed = True
    if changed:
        save_manifest(entries)
    return results


# ── GUI modal ────────────────────────────────────────────────────────────────

def cmd_gui():
    try:
        import tkinter as tk
        from tkinter import ttk, messagebox, simpledialog
    except ImportError:
        print("tkinter not available — use CLI commands instead.")
        return

    root = tk.Tk()
    root.title("Tableau PAT Keeper")
    root.resizable(False, False)

    # Header
    tk.Label(root, text="Tableau PAT Keeper", font=("Helvetica", 15, "bold")).grid(row=0, column=0, columnspan=4, pady=(14, 4))
    tk.Label(root, text="PATs are stored in macOS Keychain / Windows Credential Manager. Refresh signs in/out to reset the 15-day timer.", fg="gray").grid(row=1, column=0, columnspan=4)

    # Entry list
    frame = tk.Frame(root)
    frame.grid(row=2, column=0, columnspan=4, padx=14, pady=8)
    cols = ("label", "server_url", "site_url", "pat_name", "last_refresh")
    headers = ("Label", "Server URL", "Site URI", "PAT Name", "Last Refreshed")
    tree = ttk.Treeview(frame, columns=cols, show="headings", height=8, selectmode="browse")
    for col, hdr in zip(cols, headers):
        tree.heading(col, text=hdr)
        tree.column(col, width=160 if col != "last_refresh" else 190, anchor="w")
    scroll = ttk.Scrollbar(frame, orient="vertical", command=tree.yview)
    tree.configure(yscrollcommand=scroll.set)
    tree.pack(side="left", fill="both")
    scroll.pack(side="right", fill="y")

    def refresh_tree():
        for row in tree.get_children():
            tree.delete(row)
        for e in load_manifest():
            tree.insert("", "end", iid=manifest_key(e["site_url"], e["pat_name"]),
                        values=(e.get("label", ""), e["server_url"], e["site_url"],
                                e["pat_name"], fmt_refresh(e.get("last_refresh"))))

    refresh_tree()

    # Add/Edit form
    form = tk.LabelFrame(root, text="Add / Update PAT", padx=10, pady=8)
    form.grid(row=3, column=0, columnspan=4, padx=14, pady=4, sticky="ew")

    # (label, placeholder text shown in gray when empty)
    fields = [
        ("Label (optional)",  "e.g. The Outpost"),
        ("Server URL",        "e.g. https://prod-useast-a.online.tableau.com"),
        ("Site URI",          "e.g. DataArcade  (from the URL after /site/)"),
        ("PAT Name",          "e.g. claude-code"),
        ("PAT Secret",        "paste secret here"),
    ]
    entries_vars: list[tk.StringVar] = []
    entry_widgets: list[tk.Entry] = []

    def _make_placeholder(entry: tk.Entry, var: tk.StringVar, placeholder: str, is_secret: bool):
        if not placeholder:
            return

        def on_focus_in(_e):
            if var.get() == placeholder:
                var.set("")
                entry.config(fg="black", show="*" if is_secret else "")

        def on_focus_out(_e):
            if not var.get():
                entry.config(fg="gray", show="")
                var.set(placeholder)

        var.set(placeholder)
        entry.config(fg="gray")
        entry.bind("<FocusIn>", on_focus_in)
        entry.bind("<FocusOut>", on_focus_out)

    for row_i, (lbl, placeholder) in enumerate(fields):
        tk.Label(form, text=lbl, anchor="w", width=22).grid(row=row_i, column=0, sticky="w", pady=2)
        var = tk.StringVar()
        entries_vars.append(var)
        is_secret = "Secret" in lbl
        entry = tk.Entry(form, textvariable=var, width=52)
        entry.grid(row=row_i, column=1, sticky="ew", padx=4)
        entry_widgets.append(entry)
        _make_placeholder(entry, var, placeholder, is_secret)

    lbl_var, server_var, site_var, name_var, secret_var = entries_vars

    def _real_value(var: tk.StringVar, placeholder: str) -> str:
        """Return empty string if the field still holds its placeholder."""
        val = var.get().strip()
        return "" if val == placeholder else val

    # Tracks which existing entry the form was loaded from (site|name key), or None for new.
    editing_key: list["str | None"] = [None]

    def do_add_or_update():
        placeholders = [ph for _, ph in fields]
        label  = _real_value(lbl_var,    placeholders[0])
        server = _real_value(server_var, placeholders[1]).rstrip("/")
        site   = _real_value(site_var,   placeholders[2])
        name   = _real_value(name_var,   placeholders[3])
        secret = _real_value(secret_var, placeholders[4])

        if not server or not site or not name:
            messagebox.showerror("Missing fields", "Server URL, Site URI and PAT Name are required.")
            return

        orig_key = editing_key[0]

        if orig_key is not None:
            # Editing an existing entry
            orig_site, orig_name = orig_key.split("|", 1)
            key_changed = (site != orig_site or name != orig_name)

            if key_changed:
                # Site URL or PAT name was corrected — need a secret to create the new entry
                if not secret:
                    messagebox.showerror("Secret required",
                        "Site URI or PAT Name changed — enter the PAT Secret to save the corrected entry.")
                    return
                cmd_remove(orig_site, orig_name)
                cmd_add(server, site, name, secret, label)
                messagebox.showinfo("Updated", f"Entry updated: {site} / {name}")
            else:
                # Key unchanged — update server/label in manifest, update secret only if provided
                entries = load_manifest()
                for e in entries:
                    if e["site_url"] == site and e["pat_name"] == name:
                        e["server_url"] = server
                        e["label"] = label or f"{site} / {name}"
                        break
                save_manifest(entries)
                if secret:
                    store_secret(site, name, secret)
                messagebox.showinfo("Updated", f"PAT updated: {site} / {name}")
        else:
            # New entry
            if not secret:
                messagebox.showerror("Missing fields", "PAT Secret is required for new entries.")
                return
            if entry_exists(load_manifest(), site, name):
                messagebox.showerror("Already exists",
                    f"An entry for {site} / {name} already exists. Select it from the list to edit it.")
                return
            cmd_add(server, site, name, secret, label)
            messagebox.showinfo("Added", f"PAT added: {site} / {name}")

        editing_key[0] = None
        refresh_tree()

    def do_remove():
        sel = tree.focus()
        if not sel:
            messagebox.showwarning("Nothing selected", "Select a row first.")
            return
        site, name = sel.split("|", 1)
        if messagebox.askyesno("Remove", f"Remove {site} / {name}?"):
            cmd_remove(site, name)
            editing_key[0] = None
            refresh_tree()

    def do_populate_form():
        sel = tree.focus()
        if not sel:
            return
        entries = load_manifest()
        site, name = sel.split("|", 1)
        match = next((e for e in entries if e["site_url"] == site and e["pat_name"] == name), None)
        if match:
            editing_key[0] = manifest_key(site, name)
            # Set real values with black text (overrides any placeholder state)
            for var, widget, val in [
                (lbl_var,    entry_widgets[0], match.get("label", "")),
                (server_var, entry_widgets[1], match["server_url"]),
                (site_var,   entry_widgets[2], match["site_url"]),
                (name_var,   entry_widgets[3], match["pat_name"]),
            ]:
                var.set(val)
                widget.config(fg="black", show="")
            # Secret always blank when editing — show placeholder
            secret_var.set(fields[4][1] or "")
            entry_widgets[4].config(fg="gray", show="")

    def _show_refresh_results(results: list[dict]):
        refresh_tree()
        if not results:
            messagebox.showinfo("Refresh", "No PATs configured.")
            return
        lines = []
        for r in results:
            icon = "✓" if r["ok"] else "✗"
            lines.append(f"{icon}  {r['label']}")
            if not r["ok"]:
                lines.append(f"    {r['msg']}")
        messagebox.showinfo("Refresh complete", "\n".join(lines))

    def do_refresh_selected():
        sel = tree.focus()
        if not sel:
            messagebox.showwarning("Nothing selected", "Select a row to refresh it.")
            return
        site, name = sel.split("|", 1)
        entries = load_manifest()
        entry = next((e for e in entries if e["site_url"] == site and e["pat_name"] == name), None)
        if not entry:
            return
        secret = get_secret(site, name)
        if not secret:
            messagebox.showerror("No secret", f"No secret found in keychain for {site} / {name}.")
            return
        from datetime import datetime
        ok, msg = refresh_pat(site, name, secret, entry["server_url"])
        label = entry.get("label") or f"{site} / {name}"
        log(f"{'OK   ' if ok else 'FAIL '}{label}: {msg}")
        if ok:
            entry["last_refresh"] = datetime.now().isoformat()
            save_manifest(entries)
        refresh_tree()
        icon = "✓" if ok else "✗"
        messagebox.showinfo("Refresh", f"{icon}  {label}" + ("" if ok else f"\n    {msg}"))

    def do_refresh_all():
        if messagebox.askyesno("Refresh All", "Sign in/out for every stored PAT now?"):
            _show_refresh_results(cmd_refresh())

    def do_new_pat():
        """Clear the form and deselect the tree, ready to add a fresh entry."""
        for sel in tree.selection():
            tree.selection_remove(sel)
        editing_key[0] = None
        for var, widget, (_, placeholder) in zip(entries_vars, entry_widgets, fields):
            var.set(placeholder)
            widget.config(fg="gray", show="")

    tree.bind("<<TreeviewSelect>>", lambda _: do_populate_form())

    # Buttons
    btn_frame = tk.Frame(root)
    btn_frame.grid(row=4, column=0, columnspan=4, pady=(4, 14))
    tk.Button(btn_frame, text="New PAT",             width=12, command=do_new_pat).pack(side="left", padx=6)
    tk.Button(btn_frame, text="Save",                width=10, command=do_add_or_update).pack(side="left", padx=6)
    tk.Button(btn_frame, text="Remove Selected",     width=18, command=do_remove).pack(side="left", padx=6)
    tk.Button(btn_frame, text="Refresh Selected",    width=18, command=do_refresh_selected).pack(side="left", padx=6)
    tk.Button(btn_frame, text="Refresh All",         width=14, command=do_refresh_all).pack(side="left", padx=6)
    tk.Button(btn_frame, text="Close",               width=10, command=root.destroy).pack(side="left", padx=6)

    root.mainloop()


# ── Scheduler installer (cron on macOS/Linux, Task Scheduler on Windows) ─────

IS_WINDOWS = sys.platform == "win32"
TASK_NAME = "TableauPATKeeper"


def cmd_install_cron():
    import subprocess
    script = os.path.abspath(__file__)
    python = sys.executable
    # Every Tuesday at noon, local time.
    # cron: minute hour day month weekday  (2 = Tuesday)
    # schtasks: weekly on TUE at 12:00

    if IS_WINDOWS:
        cmd = [
            "schtasks", "/create", "/f",
            "/tn", TASK_NAME,
            "/tr", f'"{python}" "{script}" refresh',
            "/sc", "weekly",
            "/d", "TUE",
            "/st", "12:00",
            "/rl", "HIGHEST",
        ]
        result = subprocess.run(cmd, capture_output=True, text=True)
        if result.returncode == 0:
            print(f"Scheduled task '{TASK_NAME}' created (every Tuesday at 12:00 noon, local time).")
        else:
            print(f"Failed to create scheduled task:\n{result.stderr}")
        return

    # macOS / Linux: crontab — uses the system local time zone
    cron_line = f"0 12 * * 2 {python} {script} refresh"
    result = subprocess.run(["crontab", "-l"], capture_output=True, text=True)
    existing = result.stdout if result.returncode == 0 else ""
    if cron_line in existing:
        print("Cron job already installed (every Tuesday at 12:00 noon, local time).")
        return
    lines = [l for l in existing.splitlines() if "pat_keeper" not in l and "tableau-pat-keeper" not in l]
    lines.append(cron_line)
    proc = subprocess.run(["crontab", "-"], input="\n".join(lines) + "\n", text=True)
    if proc.returncode == 0:
        print(f"Cron job installed: every Tuesday at 12:00 noon, local time.")
    else:
        print("Failed to install cron job.")


def cmd_uninstall_cron():
    import subprocess

    if IS_WINDOWS:
        result = subprocess.run(
            ["schtasks", "/delete", "/f", "/tn", TASK_NAME],
            capture_output=True, text=True,
        )
        if result.returncode == 0:
            print(f"Scheduled task '{TASK_NAME}' removed.")
        else:
            print(f"Task not found or could not be removed:\n{result.stderr}")
        return

    result = subprocess.run(["crontab", "-l"], capture_output=True, text=True)
    if result.returncode != 0:
        print("No crontab found.")
        return
    lines = [l for l in result.stdout.splitlines() if "pat_keeper" not in l and "tableau-pat-keeper" not in l]
    subprocess.run(["crontab", "-"], input="\n".join(lines) + "\n", text=True)
    print("Cron job removed.")


# ── Entry point ───────────────────────────────────────────────────────────────

def main():
    parser = argparse.ArgumentParser(
        description="Tableau PAT Keeper — keep PATs alive by refreshing before expiry",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Commands:
  list                         List all stored PAT entries (no secrets shown)
  add                          Add a new PAT entry
  update                       Update the secret for an existing entry
  remove                       Remove a PAT entry
  refresh [--dry-run]          Sign in/out for all stored PATs (resets 15-day timer)
  gui                          Open the GUI modal (macOS / Linux with Tk)
  install-cron                 Schedule auto-refresh every Tuesday at 12:00 noon (local time)
  uninstall-cron               Remove the auto-refresh schedule

Examples:
  pat_keeper.py add --server https://prod-useast-a.online.tableau.com --site mysite --pat-name mykey --pat-secret xxxxxxxxxxx
  pat_keeper.py list
  pat_keeper.py gui
  pat_keeper.py refresh
  pat_keeper.py install-cron
""")
    sub = parser.add_subparsers(dest="cmd")

    sub.add_parser("list", help="List stored PATs")

    p_add = sub.add_parser("add", help="Add a PAT")
    p_add.add_argument("--server", required=True)
    p_add.add_argument("--site", required=True)
    p_add.add_argument("--pat-name", required=True)
    p_add.add_argument("--pat-secret", required=True)
    p_add.add_argument("--label", default="")

    p_upd = sub.add_parser("update", help="Update a PAT secret")
    p_upd.add_argument("--server", required=True)
    p_upd.add_argument("--site", required=True)
    p_upd.add_argument("--pat-name", required=True)
    p_upd.add_argument("--pat-secret", required=True)

    p_rm = sub.add_parser("remove", help="Remove a PAT entry")
    p_rm.add_argument("--site", required=True)
    p_rm.add_argument("--pat-name", required=True)

    p_ref = sub.add_parser("refresh", help="Refresh all PATs")
    p_ref.add_argument("--dry-run", action="store_true")

    sub.add_parser("gui", help="Open GUI modal")

    sub.add_parser("install-cron", help="Schedule auto-refresh every Tuesday at noon (local time)")

    sub.add_parser("uninstall-cron", help="Remove cron job")

    args = parser.parse_args()

    if not KEYRING_AVAILABLE and args.cmd not in ("list", "refresh", "install-cron", "uninstall-cron", None):
        print("WARNING: 'keyring' package not installed. Secrets cannot be stored safely.")
        print("Run: pip install keyring requests")

    if args.cmd == "list":
        cmd_list()
    elif args.cmd == "add":
        cmd_add(args.server, args.site, args.pat_name, args.pat_secret, args.label)
    elif args.cmd == "update":
        cmd_update(args.server, args.site, args.pat_name, args.pat_secret)
    elif args.cmd == "remove":
        cmd_remove(args.site, args.pat_name)
    elif args.cmd == "refresh":
        results = cmd_refresh(dry_run=args.dry_run)
        if results:
            ok_count = sum(1 for r in results if r["ok"])
            fail_count = len(results) - ok_count
            if fail_count:
                title = f"PAT Keeper: {fail_count} refresh(es) failed"
                body = "; ".join(r["label"] for r in results if not r["ok"])
            else:
                title = f"PAT Keeper: {ok_count} PAT(s) refreshed"
                body = "; ".join(r["label"] for r in results)
            import subprocess as _sp
            _sp.run(
                ["/opt/homebrew/bin/terminal-notifier",
                 "-title", title,
                 "-message", body],
                check=False,
            )
    elif args.cmd == "gui":
        cmd_gui()
    elif args.cmd == "install-cron":
        cmd_install_cron()
    elif args.cmd == "uninstall-cron":
        cmd_uninstall_cron()
    else:
        parser.print_help()


if __name__ == "__main__":
    main()
