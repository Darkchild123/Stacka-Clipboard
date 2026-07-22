# ============================================================
# ClipDrop - main.py
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

# Silence benign DirectWrite font warnings: Qt's glyph fallback (emoji in
# labels) enumerates legacy Windows BITMAP fonts (8514oem, Fixedsys) that
# DirectWrite cannot load. Text renders fine via the next fallback — the
# console noise is useless and alarming, so drop that log category.
os.environ.setdefault("QT_LOGGING_RULES", "qt.qpa.fonts.warning=false")

from PyQt6.QtWidgets import QApplication
from PyQt6.QtCore    import Qt

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
    print("ClipDrop is starting...")

    # Step 1: QApplication — must exist before any QWidget is created
    app = QApplication(sys.argv)
    app.setQuitOnLastWindowClosed(False)   # keep running after popup closes

    # Step 2: History Manager
    history = HistoryManager()

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
    app.setProperty("clipdrop_popup", popup)

    # Step 6: Context Menu — setup() starts its own internal daemon threads
    # for mouse hook and signal file watcher; the call itself returns quickly.
    # MUST be called on the main thread so QTimer / QWidget creation works.
    context = ContextMenu(history, popup)
    context.setup()
    # Expose app-wide so the Shortcuts window can re-bind the hotkey live
    app.setProperty("clipdrop_context", context)

    # Step 7: Tray Icon — start() schedules tray creation via QTimer;
    # must be called on the main thread.
    tray = TrayIcon(history, profiles)
    tray.start()
    # Expose the tray app-wide so DropdownPopup._show_toast can post
    # balloon notifications without a circular import.
    app.setProperty("clipdrop_tray", tray)

    print("ClipDrop is running.")
    print("  Right-click anywhere → 'Paste from ClipDrop'")
    print("  Or press Ctrl+Shift+V from any app")

    try:
        sys.exit(app.exec())
    except KeyboardInterrupt:
        print("ClipDrop interrupted.")
    finally:
        try:
            context.teardown()
        except Exception:
            pass
        print("ClipDrop closed.")


if __name__ == "__main__":
    main()
