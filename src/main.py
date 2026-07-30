# ============================================================
# Stacka - main.py
# ============================================================
# App entry point. Starts all components in the correct order.
#
# PyQt6 owns the main thread via app.exec().
# Background-only components (clipboard watcher, mouse hook,
# signal file watcher) run on daemon threads.
# UI components are created on the main thread.
# ============================================================

import os
import threading
import sys

# NOTE on GIL vs the mouse hook — do not "fix" this with sys.setswitchinterval.
# Windows delivers no mouse event to ANY app until the WH_MOUSE_LL hook in
# context_menu.py returns, and that callback is Python, so it needs the GIL.
# Lowering the switch interval to 1 ms looks like it should help, and was tried:
# measured against a realistic rebuild it changed nothing (max hook stall 5.6 ms
# vs 7.1 ms — noise), because PyQt already releases the GIL around every Qt
# call, which keeps the hook thread fed. What actually matters is doing less
# work on the main thread; see the UI notes in CLAUDE.md.

# ── Claim Per-Monitor-v2 DPI awareness FIRST ────────────────────────────────
# This MUST run before anything imports pyautogui: pyautogui calls the old
# SetProcessDPIAware() at import time, forcing System-DPI mode, which then
# makes Qt's own Per-Monitor setup fail ("SetProcessDpiAwarenessContext:
# Access is denied") and mismatches coordinates and layout on scaled
# displays (125% / 150%) — the popup lands off-cursor and rows stop
# resizing. Setting Per-Monitor-v2 here, before those imports, makes Qt and
# the process agree on one coordinate system.
def _set_dpi_awareness():
    import ctypes
    try:                        # Win10 1703+ : Per-Monitor-Aware v2
        if ctypes.windll.user32.SetProcessDpiAwarenessContext(
                ctypes.c_void_p(-4)):
            return
    except Exception:
        pass
    try:                        # Win8.1+ fallback : Per-Monitor-Aware
        ctypes.windll.shcore.SetProcessDpiAwareness(2)
    except Exception:
        pass
_set_dpi_awareness()


# ── "--paste-signal" mode ───────────────────────────────────────────────────
# The Explorer / Desktop right-click entry ("Paste from Stacka") can't call
# into the already-running app directly, so it drops a signal file carrying the
# cursor position; the running instance watches for it and opens the popup
# there (see ContextMenu._watch_signal_file).
#
# The registry command used to be `pythonw.exe -c "<python>"`, which only works
# when the app runs from source — the FROZEN Stacka.exe is not a Python
# interpreter, so `Stacka.exe -c "..."` just launched a second copy of the app
# instead of opening the popup. Now the exe (or main.py) is invoked with
# --paste-signal and does the job itself.
#
# This runs BEFORE the PyQt6 imports so the helper process starts, writes one
# small file and exits in milliseconds — it never builds a UI.
def _write_paste_signal():
    import ctypes, tempfile

    class _PT(ctypes.Structure):
        _fields_ = [("x", ctypes.c_long), ("y", ctypes.c_long)]

    pt = _PT()
    try:
        ctypes.windll.user32.GetCursorPos(ctypes.byref(pt))
    except Exception:
        return 1
    try:
        path = os.path.join(tempfile.gettempdir(), "stacka.signal")
        with open(path, "w", encoding="utf-8") as f:
            f.write(f"Point(x={pt.x}, y={pt.y})")
    except Exception:
        return 1
    return 0


if "--paste-signal" in sys.argv:
    sys.exit(_write_paste_signal())


# Redirect stdout/stderr to %APPDATA%\Stacka\stacka.log. A --windowed build
# has no console (print() would vanish), so this is the only diagnostic trail —
# and it also captures uncaught tracebacks. Placed AFTER the --paste-signal exit
# so the short-lived helper process never opens the log, and BEFORE the heavy
# imports so an import-time failure is recorded too. Running from source, output
# still appears on the console as well.
import applog
applog.setup()


def _set_app_user_model_id():
    # Windows: give the process its own taskbar identity so it shows Stacka's
    # icon (not the Python launcher's) and pins / groups as its own app.
    import ctypes
    try:
        ctypes.windll.shell32.SetCurrentProcessExplicitAppUserModelID("Cosmas.Stacka")
    except Exception:
        pass
_set_app_user_model_id()

# Silence benign DirectWrite font warnings: Qt's glyph fallback (emoji in
# labels) enumerates legacy Windows BITMAP fonts (8514oem, Fixedsys) that
# DirectWrite cannot load. Text renders fine via the next fallback — the
# console noise is useless and alarming, so drop that log category.
os.environ.setdefault("QT_LOGGING_RULES", "qt.qpa.fonts.warning=false")

from PyQt6.QtWidgets import QApplication
from PyQt6.QtCore    import Qt
from PyQt6.QtGui     import QIcon

from app_paths import resource_path
import i18n

from clipboard_watcher import ClipboardWatcher
from history_manager   import HistoryManager
from profile_manager   import ProfileManager
from tray_icon         import TrayIcon
from context_menu      import ContextMenu
from dropdown_popup    import DropdownPopup


def protected_thread(name, target, *args, **kwargs):
    """Wraps a function in a background daemon thread with crash protection."""
    def safe_run():
        try:
            target(*args, **kwargs)
        except Exception as e:
            print(f"[{name}] crashed: {e}")
            import traceback
            traceback.print_exc()

    thread = threading.Thread(target=safe_run, daemon=True)
    thread.name = name
    thread.start()
    return thread


def main():
    print("Stacka is starting...")

    # Step 1: QApplication — must exist before any QWidget is created
    app = QApplication(sys.argv)
    app.setQuitOnLastWindowClosed(False)   # keep running after popup closes

    # App-wide window icon — taskbar, Alt+Tab, and every window's title bar.
    # Prefer the multi-size .ico (Windows picks the crispest per context),
    # fall back to the PNG. resource_path() locates them in the bundle when frozen.
    for _name in ("stacka.ico", "icon.png"):
        _p = resource_path("assets", _name)
        if os.path.exists(_p):
            app.setWindowIcon(QIcon(_p))
            break

    # Step 2: History Manager
    history = HistoryManager()

    # Apply the saved UI language before any window is built.
    i18n.set_language(history.settings.get("language", "en"))

    # Step 3: Profile Manager
    profiles = ProfileManager(history)

    # Step 4: Clipboard Watcher — purely background, safe to thread
    watcher = ClipboardWatcher(history)
    protected_thread("ClipboardWatcher", watcher.start)

    # Step 5: Dropdown Popup — QObject lives on main thread
    popup = DropdownPopup(history_manager=history, watcher=watcher,
                          profile_manager=profiles)
    # Expose app-wide so the settings panel can live-apply theme /
    # transparency changes to an open popup.
    app.setProperty("stacka_popup", popup)

    # Step 6: Context Menu — setup() starts its own internal daemon threads
    # for mouse hook and signal file watcher; the call itself returns quickly.
    # MUST be called on the main thread so QTimer / QWidget creation works.
    context = ContextMenu(history, popup)
    context.setup()
    # Expose app-wide so the Shortcuts window can re-bind the hotkey live
    app.setProperty("stacka_context", context)

    # Step 7: Tray Icon — start() schedules tray creation via QTimer;
    # must be called on the main thread.
    tray = TrayIcon(history, profiles)
    tray.start()
    # Expose the tray app-wide so DropdownPopup._show_toast can post
    # balloon notifications without a circular import.
    app.setProperty("stacka_tray", tray)

    # Step 8: Auto-wipe — run any schedule that fell due while the app was
    # closed, then check hourly. Pinned items are always kept.
    import auto_wipe
    from PyQt6.QtCore import QTimer
    auto_wipe.run_if_due(history, profiles)
    _wipe_timer = QTimer()
    _wipe_timer.timeout.connect(lambda: auto_wipe.run_if_due(history, profiles))
    _wipe_timer.start(60 * 60 * 1000)          # hourly
    app.setProperty("stacka_wipe_timer", _wipe_timer)   # keep a reference alive

    print("Stacka is running.")
    print("  Right-click anywhere → 'Paste from Stacka'")
    print("  Or press Ctrl+Shift+V from any app")

    try:
        sys.exit(app.exec())
    except KeyboardInterrupt:
        print("Stacka interrupted.")
    finally:
        try:
            context.teardown()
        except Exception:
            pass
        print("Stacka closed.")


if __name__ == "__main__":
    main()
