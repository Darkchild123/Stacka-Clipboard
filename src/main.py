# ============================================================
# ClipDrop - main.py
# ============================================================
# App entry point. Starts all components in the correct order.
#
# tkinter owns the main thread via root.mainloop().
# All other components run on background daemon threads.
# Each thread is wrapped in crash protection so one failure
# never takes down the entire app.
# ============================================================

import threading
import sys
import tkinter as tk
from clipboard_watcher import ClipboardWatcher
from history_manager import HistoryManager
from tray_icon import TrayIcon
from context_menu import ContextMenu
from dropdown_popup import DropdownPopup


def protected_thread(name, target, *args, **kwargs):
    """
    Wraps a function in a background thread with crash protection.
    If the function crashes, it prints the error and keeps the app alive
    instead of silently killing the whole process.
    """
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

    # Step 1: Create the tkinter root window
    # MUST happen on the main thread before anything else.
    root = tk.Tk()
    root.withdraw()  # Hide immediately — it is the engine, not a visible window

    # Catch any unhandled tkinter errors so they don't kill the app
    def handle_tk_error(exc, val, tb):
        import traceback
        print(f"[tkinter error] {val}")
        traceback.print_exception(exc, val, tb)

    root.report_callback_exception = handle_tk_error

    # Step 2: History Manager — loads saved clipboard data from disk
    history = HistoryManager()

    # Step 3: Clipboard Watcher — monitors copy events in background
    watcher = ClipboardWatcher(history)
    protected_thread("ClipboardWatcher", watcher.start)

    # Step 4: Dropdown Popup — the visual clipboard list
    popup = DropdownPopup(root, history, watcher)

    # Step 5: Context Menu — right-click integration and hotkey
    context = ContextMenu(history, popup, root)
    protected_thread("ContextMenu", context.setup)

    # Step 6: Tray Icon — system tray icon and menu
    tray = TrayIcon(history, root)
    protected_thread("TrayIcon", tray.start)

    print("ClipDrop is running.")
    print("  Right-click anywhere → '📋 Paste from ClipDrop' button appears")
    print("  Or press Ctrl+Shift+V from any app")

    # Step 7: tkinter main loop — keeps the app alive
    # Runs until root.destroy() is called (user clicks Quit)
    try:
        root.mainloop()
    except KeyboardInterrupt:
        print("ClipDrop interrupted.")
    finally:
        context.teardown()
        print("ClipDrop closed.")


if __name__ == "__main__":
    main()
