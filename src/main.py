# ============================================================
# ClipDrop - main.py
# ============================================================
# App entry point. Starts all components in the correct order.
#
# FIX: Resolved architecture conflict between tkinter and pystray.
# tkinter MUST run on the main thread — so we move pystray and
# all other components to background threads, and let tkinter's
# mainloop() own the main thread.
# ============================================================

import threading
import sys
import tkinter as tk
from clipboard_watcher import ClipboardWatcher
from history_manager import HistoryManager
from tray_icon import TrayIcon
from context_menu import ContextMenu
from dropdown_popup import DropdownPopup


def main():
    print("ClipDrop is starting...")

    # Step 1: Create the tkinter root window
    # This MUST happen on the main thread before anything else.
    # All popup operations will run through this root.
    root = tk.Tk()
    root.withdraw()  # Hide it immediately — it's just the engine

    # Step 2: Start the History Manager
    history = HistoryManager()

    # Step 3: Start the Clipboard Watcher on a background thread
    watcher = ClipboardWatcher(history)
    watcher_thread = threading.Thread(target=watcher.start, daemon=True)
    watcher_thread.start()

    # Step 4: Create the Dropdown Popup
    # We pass the watcher so the popup can pause it during paste
    # preventing our own paste from being recorded as a new copy
    popup = DropdownPopup(root, history, watcher)

    # Step 5: Set up the Context Menu and hotkey on a background thread
    # We pass the popup so it can trigger show() when needed
    context = ContextMenu(history, popup, root)
    context_thread = threading.Thread(target=context.setup, daemon=True)
    context_thread.start()

    # Step 6: Start the Tray Icon on a background thread
    # pystray runs happily on a background thread
    tray = TrayIcon(history, root)
    tray_thread = threading.Thread(target=tray.start, daemon=True)
    tray_thread.start()

    print("ClipDrop is running. Press Ctrl+Shift+V to open clipboard history.")

    # Step 7: Hand control to tkinter's main loop
    # This keeps the app alive and processes all UI events.
    # The app runs here until root.destroy() is called (on quit).
    root.mainloop()

    # Cleanup after mainloop exits
    context.teardown()
    print("ClipDrop closed.")


if __name__ == "__main__":
    main()
