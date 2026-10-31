"""
Background jobs for a server that stays running.

One thread wakes every couple of minutes and runs whatever is due:

* maintenance  — daily: roll bill periods over, record the net worth snapshot,
                 drop activity history older than a year
                 (otherwise these only happen when the server starts)
* backup       — daily automatic database backup (models/backups.py)
* simplefin    — balances (and new transactions) every N hours, if turned on
* digest       — the daily email (models/alerts.py)
* push         — new alerts and the morning summary to your phone (models/notify.py)

Each job's last result is kept in ``STATUS`` for Settings to show. A failing
job never stops the others or the server.
"""

from __future__ import annotations

import threading
from datetime import datetime, timedelta

TICK_SECONDS = 120
STATUS: dict[str, dict] = {}
_status_lock = threading.Lock()


def _record(job: str, ok: bool, message: str) -> None:
    with _status_lock:
        STATUS[job] = {"ok": ok, "message": message, "at": datetime.now().isoformat(timespec="seconds")}


def status() -> dict:
    with _status_lock:
        return {k: dict(v) for k, v in STATUS.items()}


# ── Individual jobs ────────────────────────────────────────────────────

def maintenance_due(now: datetime, settings: dict) -> bool:
    return settings["last_maintenance_date"] != now.date().isoformat()


def run_maintenance(manager, now: datetime) -> str:
    from models.app_settings import update_settings
    from models import activity
    reset = manager.auto_reset_periods()
    manager.record_net_worth_snapshot()
    activity.prune(now)
    update_settings({"last_maintenance_date": now.date().isoformat()})
    return f"Rolled over {reset} bill period(s); net worth recorded" if reset else "Net worth recorded"


def simplefin_due(now: datetime, settings: dict) -> bool:
    hours = settings["simplefin_auto_sync_hours"]
    if not hours:
        return False
    last = settings["last_simplefin_sync"]
    try:
        return not last or now - datetime.fromisoformat(last) >= timedelta(hours=hours)
    except ValueError:
        return True


def run_simplefin_sync(manager, now: datetime | None = None) -> str:
    """Pull balances for mapped accounts and (optionally) new transactions."""
    from models.app_settings import get_settings, update_settings
    from models.simplefin import (SimplefinClient, get_simplefin_connection, get_simplefin_mappings,
                                  update_simplefin_last_sync)
    now = now or datetime.now()
    s = get_settings()
    # Record the attempt first, so a broken connection is retried next interval, not every tick
    update_settings({"last_simplefin_sync": now.isoformat(timespec="seconds")})
    conn = get_simplefin_connection()
    mappings = get_simplefin_mappings()
    if not conn or not mappings:
        raise ValueError("SimpleFIN isn't connected, or no accounts are mapped")
    result = SimplefinClient.sync_balances(conn["access_url"], mappings, manager)
    if result.accounts_updated and hasattr(manager, "invalidate_plan_cache"):
        manager.invalidate_plan_cache()
    update_simplefin_last_sync()
    parts = [f"{result.accounts_updated} balance(s) updated"]
    if s["simplefin_auto_import"]:
        from models import ledger
        out = ledger.import_simplefin(14)
        parts.append(f"{out['imported']} new transaction(s)")
        try:
            from models.bill_matching import auto_match
            matched = auto_match(manager)
            if matched:
                parts.append(f"{matched} bill(s) matched")
        except ImportError:
            pass
        manager.apply_settings(get_settings())  # learned spending may have changed
    if result.errors:
        parts.append(f"{len(result.errors)} error(s)")
    message = ", ".join(parts)
    update_settings({"last_simplefin_result": f"{now:%b %d %H:%M}: {message}"})
    return message


# ── The loop ───────────────────────────────────────────────────────────

def run_due_jobs(state: dict, lock, now: datetime | None = None) -> dict:
    """Run every job that's due now. Returns {job: message} for those that ran."""
    from models import alerts, backups, notify
    from models.app_settings import get_settings
    now = now or datetime.now()
    s = get_settings()
    ran: dict[str, str] = {}

    def attempt(job, fn):
        try:
            with lock:
                msg = fn(state["manager"])
            if msg:
                _record(job, True, msg)
                ran[job] = msg
        except Exception as e:  # noqa: BLE001 — one job failing must not stop the rest
            _record(job, False, str(e))
            ran[job] = f"failed: {e}"
            print(f"⚠️  {job} job failed: {e}")

    if maintenance_due(now, s):
        attempt("maintenance", lambda m: run_maintenance(m, now))
    if backups.backup_due(now):
        attempt("backup", lambda m: backups.run_scheduled(now))
    if simplefin_due(now, s):
        attempt("simplefin", lambda m: run_simplefin_sync(m, now))
    if alerts.digest_due(now):
        attempt("digest", lambda m: alerts.send_digest(m))
    if s["push_enabled"] and s["ntfy_url"]:
        attempt("push", lambda m: (f"{n} alert(s) pushed" if (n := notify.push_new_alerts(m)) else ""))
        if notify.summary_due(now):
            attempt("push_summary", lambda m: notify.push_summary(m, now))
    return ran


def start(app) -> threading.Thread:
    """Start the background thread for this app."""
    state, lock = app.config["BUDGET_STATE"], app.config["BUDGET_LOCK"]
    stop = threading.Event()

    def loop():
        while not stop.is_set():
            for job, msg in run_due_jobs(state, lock).items():
                print(f"⏱  {job}: {msg}")
            stop.wait(TICK_SECONDS)

    thread = threading.Thread(target=loop, daemon=True, name="budget-jobs")
    thread.stop = stop  # type: ignore[attr-defined]
    thread.start()
    return thread
