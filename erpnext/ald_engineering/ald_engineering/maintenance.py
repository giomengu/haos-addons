"""Authenticated native Frappe backup operations for the future ALD Engineering app.

This module must be installed as part of the Frappe Python app before use.
No unauthenticated web routes or shell command parameters are exposed.
"""
import os
import subprocess
from pathlib import Path
import frappe

BENCH = Path("/home/frappe/frappe-bench")
SITE = "frontend"

def _require_admin():
    if frappe.session.user != "Administrator":
        frappe.throw("Administrator access required", frappe.PermissionError)

@frappe.whitelist(methods=["POST"])
def create_backup():
    """Queue a database + public/private file backup; return the job id."""
    _require_admin()
    job = frappe.enqueue(
        "ald_engineering.maintenance._run_backup",
        queue="long",
        timeout=3600,
        job_name="ALD full Frappe backup",
        enqueue_after_commit=True,
    )
    return {"job_id": job.id}

def _run_backup():
    """Worker-only function; never expose as a whitelisted endpoint."""
    site = frappe.local.site
    if site != SITE:
        raise RuntimeError("Unexpected Frappe site")
    command = ["bench", "--site", SITE, "backup", "--with-files"]
    result = subprocess.run(
        command, cwd=str(BENCH), capture_output=True, text=True,
        timeout=3300, check=False,
        env={**os.environ, "HOME": "/home/frappe"},
    )
    if result.returncode:
        frappe.log_error(
            title="ALD native backup failed",
            message=(result.stderr or result.stdout)[-6000:],
        )
        raise RuntimeError("Native Frappe backup failed; consult Error Log")
    return {"ok": True}

@frappe.whitelist(methods=["GET"])
def list_backups():
    """Return metadata only; no raw file path or download endpoint."""
    _require_admin()
    backup_dir = BENCH / "sites" / SITE / "private" / "backups"
    if not backup_dir.is_dir():
        return []
    items = []
    for path in sorted(backup_dir.iterdir(), key=lambda p: p.stat().st_mtime, reverse=True)[:50]:
        if not path.is_file() or path.is_symlink():
            continue
        stat = path.stat()
        items.append({"name": path.name, "size_bytes": stat.st_size, "modified": stat.st_mtime})
    return items
