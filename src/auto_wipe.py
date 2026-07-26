# ============================================================
# Stacka - auto_wipe.py
# ============================================================
# Optional scheduled clear-out of the clipboard history.
#
# A clipboard manager accumulates everything you copy — including things you
# would rather not keep for months. Auto-wipe empties it on a schedule so old
# clips do not pile up indefinitely.
#
# PINNED ITEMS ARE ALWAYS KEPT. Pinning means "never remove this
# automatically", so auto-wipe honours it. Only the manual Clear button
# removes pinned items.
#
# Settings keys:
#   auto_wipe       "off" | "daily" | "weekly" | "monthly" | "quarterly" | "yearly"
#   auto_wipe_last  ISO-8601 timestamp of the last wipe (or the moment the
#                   schedule was switched on, which starts the clock)
#
# The check runs at startup and hourly, so a machine that was switched off on
# the due date still wipes at the next launch rather than skipping the period.
# ============================================================

import datetime

OFF = "off"

# (settings value, label shown in Settings, days between wipes)
SCHEDULES = [
    (OFF,         "Never",     None),
    ("daily",     "Daily",       1),
    ("weekly",    "Weekly",      7),
    ("monthly",   "Monthly",    30),
    ("quarterly", "Quarterly",  91),
    ("yearly",    "Yearly",    365),
]

_DAYS = {key: days for key, _label, days in SCHEDULES}


def label_for(key: str) -> str:
    for k, lbl, _d in SCHEDULES:
        if k == key:
            return lbl
    return "Never"


def _now() -> datetime.datetime:
    return datetime.datetime.now()


def _parse(ts):
    try:
        return datetime.datetime.fromisoformat(ts)
    except (TypeError, ValueError):
        return None


def next_due(settings):
    """When the next wipe is due, or None if auto-wipe is off / unknown."""
    days = _DAYS.get(settings.get("auto_wipe", OFF))
    if not days:
        return None
    last = _parse(settings.get("auto_wipe_last"))
    if last is None:
        return None
    return last + datetime.timedelta(days=days)


def is_due(settings) -> bool:
    due = next_due(settings)
    return due is not None and _now() >= due


def start_schedule(history, key: str):
    """Record when a schedule was chosen — that starts the clock. Without it
    a freshly enabled 'monthly' would fire immediately."""
    history.save_setting("auto_wipe", key)
    if key != OFF:
        history.save_setting("auto_wipe_last", _now().isoformat(timespec="seconds"))


def run_if_due(history, profiles=None) -> bool:
    """Wipe if the schedule says so. Returns True if a wipe happened.

    Clears General AND every named profile, keeping pinned items in each.
    Safe to call often; it only acts when actually due.
    """
    try:
        settings = history.settings
        if settings.get("auto_wipe", OFF) == OFF:
            return False
        if settings.get("auto_wipe_last") is None:
            # Schedule on but never stamped (e.g. hand-edited config) — start
            # the clock now rather than wiping unexpectedly.
            history.save_setting("auto_wipe_last", _now().isoformat(timespec="seconds"))
            return False
        if not is_due(settings):
            return False

        history.clear_all(keep_pinned=True)
        if profiles is not None:
            profiles.clear_all_profiles(keep_pinned=True)
        history.save_setting("auto_wipe_last", _now().isoformat(timespec="seconds"))
        print(f"Auto-wipe ran ({settings.get('auto_wipe')}); pinned items kept.")
        return True
    except Exception as e:
        # Never let a scheduled clean-up take the app down.
        print(f"[Stacka] Auto-wipe failed: {e}")
        return False
