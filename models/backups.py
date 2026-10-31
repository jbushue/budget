"""
Database backups kept on the server, in the "backups" folder next to the database.

* automatic: once a day (Settings → Data & backup), the newest ``backup_keep`` kept
* manual: "Back up now"
* before-restore: the data a restore replaced (written by the restore route)

Only automatic backups are pruned.
"""

from __future__ import annotations

import os
import re
import sqlite3
from datetime import datetime

from models import database as db

NAME_RE = re.compile(r"^[A-Za-z0-9_.-]+\.db$")
KINDS = ("auto", "manual", "before-restore")


def backup_dir() -> str:
    path = os.path.join(os.path.dirname(db.DB_PATH), "backups")
    os.makedirs(path, exist_ok=True)
    return path


def _kind(name: str) -> str:
    return next((k for k in KINDS if name.startswith(k + "-")), "other")


def sqlite_copy(src_path: str, dst_path: str) -> None:
    """Consistent copy of a SQLite database, safe while it's in use."""
    src = sqlite3.connect(src_path)
    dst = sqlite3.connect(dst_path)
    try:
        src.backup(dst)
    finally:
        dst.close()
        src.close()


def run_backup(kind: str = "auto", now: datetime | None = None) -> dict:
    """Copy the database into the backups folder; returns the new backup's info."""
    now = now or datetime.now()
    name = f"{kind}-{now:%Y%m%d-%H%M%S}.db"
    path = os.path.join(backup_dir(), name)
    sqlite_copy(db.DB_PATH, path)
    return _info(name)


def _info(name: str) -> dict:
    path = os.path.join(backup_dir(), name)
    st = os.stat(path)
    return {"name": name, "kind": _kind(name), "size": st.st_size,
            "created": datetime.fromtimestamp(st.st_mtime).isoformat(timespec="seconds")}


def list_backups() -> list[dict]:
    names = [n for n in os.listdir(backup_dir()) if NAME_RE.match(n)]
    return sorted((_info(n) for n in names), key=lambda b: b["created"], reverse=True)


def prune(keep: int) -> list[str]:
    """Delete all but the newest ``keep`` automatic backups; returns the names removed."""
    autos = [b for b in list_backups() if b["kind"] == "auto"]
    removed = []
    for b in autos[keep:]:
        try:
            os.remove(os.path.join(backup_dir(), b["name"]))
            removed.append(b["name"])
        except OSError:
            pass
    return removed


def path_for(name: str) -> str | None:
    """Full path of a backup by name, or None (rejects anything that isn't a plain backup file name)."""
    if not NAME_RE.match(name or ""):
        return None
    path = os.path.join(backup_dir(), name)
    return path if os.path.isfile(path) else None


def delete(name: str) -> bool:
    path = path_for(name)
    if path is None:
        return False
    os.remove(path)
    return True


def backup_due(now: datetime | None = None) -> bool:
    """True when today's automatic backup hasn't been made yet (at or after the backup hour)."""
    from models.app_settings import get_settings
    now = now or datetime.now()
    s = get_settings()
    return bool(s["auto_backup"] and now.hour >= s["backup_hour"]
                and s["last_backup_date"] != now.date().isoformat())


def run_scheduled(now: datetime | None = None) -> str:
    """The daily automatic backup plus pruning. Returns a status message."""
    from models.app_settings import get_settings, update_settings
    now = now or datetime.now()
    info = run_backup("auto", now)
    removed = prune(get_settings()["backup_keep"])
    update_settings({"last_backup_date": now.date().isoformat()})
    return f"Backup {info['name']}" + (f" (removed {len(removed)} old)" if removed else "")
