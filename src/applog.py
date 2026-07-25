# ============================================================
# Stacka - applog.py
# ============================================================
# File-based logging, so a WINDOWED (no-console) build still leaves a
# diagnostic trail.
#
# A packaged Stacka is built with --windowed: Windows gives it no console,
# and PyInstaller sets sys.stdout / sys.stderr to None, which turns every
# print() into a silent no-op. That removes the console flash, but it also
# means a misbehaving build tells you nothing.
#
# setup() redirects stdout and stderr to:
#     <user data>/stacka.log      (%APPDATA%\Stacka\stacka.log when packaged)
# so all the existing print() calls — and any uncaught traceback — are written
# there instead. No existing code has to change.
#
# When a real console IS present (running from source) output is TEE'd: it
# still appears on screen and is also written to the log, so the dev workflow
# is unchanged.
#
# PRIVACY: the log is a PLAINTEXT file, while the clipboard stores are
# encrypted at rest (see secure_store.py). It must therefore never contain
# clipboard content or its metadata — no copied text, no source window titles,
# no card details, no file paths. Log that something happened and of what
# TYPE, never what it was. Keep that rule when adding new print() calls.
# ============================================================

import datetime
import os
import sys
import threading

LOG_NAME  = "stacka.log"
MAX_BYTES = 1_000_000        # rotate at ~1 MB, keeping one .1 backup

_installed = False


def log_path() -> str:
    from app_paths import user_data_root
    return os.path.join(user_data_root(), LOG_NAME)


def _stamp() -> str:
    return datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")


class _LogWriter:
    """File-like object: timestamps each line into the log, and mirrors to the
    real console when there is one. Never raises — logging must not be able to
    take the app down."""

    def __init__(self, fh, console, lock):
        self._fh       = fh
        self._console  = console
        self._lock     = lock
        self._new_line = True

    def write(self, text):
        if not text:
            return 0
        try:
            if self._console is not None:
                self._console.write(text)
                self._console.flush()
        except Exception:
            pass
        try:
            with self._lock:
                for part in text.splitlines(keepends=True):
                    if self._new_line and part.strip():
                        self._fh.write(_stamp() + "  ")
                    self._fh.write(part)
                    self._new_line = part.endswith(("\n", "\r"))
                self._fh.flush()
        except Exception:
            pass
        return len(text)

    def flush(self):
        for s in (self._console, self._fh):
            try:
                if s is not None:
                    s.flush()
            except Exception:
                pass

    def isatty(self):
        return False

    def fileno(self):          # some libraries probe this
        raise OSError("Stacka log has no file descriptor")


def _rotate(path):
    try:
        if os.path.exists(path) and os.path.getsize(path) > MAX_BYTES:
            backup = path + ".1"
            if os.path.exists(backup):
                os.remove(backup)
            os.replace(path, backup)
    except Exception:
        pass


def setup():
    """Point stdout/stderr at the log file. Safe to call once, at startup."""
    global _installed
    if _installed:
        return None
    try:
        path = log_path()
        os.makedirs(os.path.dirname(path), exist_ok=True)
        _rotate(path)
        fh = open(path, "a", encoding="utf-8", errors="replace")
        lock = threading.Lock()

        sys.stdout = _LogWriter(fh, sys.stdout, lock)
        sys.stderr = _LogWriter(fh, sys.stderr, lock)

        # A windowed build has nowhere to show a crash — record it.
        def _hook(exc_type, exc, tb):
            import traceback
            try:
                sys.stderr.write("UNCAUGHT EXCEPTION\n")
                traceback.print_exception(exc_type, exc, tb, file=sys.stderr)
            except Exception:
                pass
        sys.excepthook = _hook

        _installed = True
        print(f"--- Stacka log opened ({'packaged' if getattr(sys, 'frozen', False) else 'source'}) ---")
        return path
    except Exception as e:
        try:
            print(f"[Stacka] Could not open log file: {e}")
        except Exception:
            pass
        return None
