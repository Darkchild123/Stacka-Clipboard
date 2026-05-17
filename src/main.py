# ============================================================
# ClipDrop - main.py
# ============================================================
# This is the entry point of the ClipDrop application.
# It starts up all the components and keeps the app running.
# ============================================================

import threading
import sys
from clipboard_watcher import ClipboardWatcher
from history_manager import HistoryManager
from tray_icon import TrayIcon
from context_menu import ContextMenu


def main():
    print("ClipDrop is starting...")

    # Step 1: Start the History Manager
    # This loads any previously saved clipboard history from disk
    history = HistoryManager()

    # Step 2: Start the Clipboard Watcher
    # This runs in the background and watches for anything you copy
    # We pass it the history manager so it knows where to save copied items
    watcher = ClipboardWatcher(history)
    watcher_thread = threading.Thread(target=watcher.start, daemon=True)
    watcher_thread.start()

    # Step 3: Set up the Context Menu
    # This adds "Paste from ClipDrop" to the Windows right-click menu
    # and registers the Ctrl+Shift+V hotkey
    context = ContextMenu(history)
    context.setup()

    # Step 4: Start the System Tray Icon
    # This puts the ClipDrop icon in your taskbar tray
    # We pass it the history manager so the tray can access settings and history
    tray = TrayIcon(history)
    tray.start()  # This keeps the app alive until you quit from the tray

    # When the tray exits (user clicks Quit), clean up the context menu
    context.teardown()


if __name__ == "__main__":
    main()
