# ============================================================
# ClipDrop - context_menu.py
# ============================================================
# This file handles all Windows right-click context menu
# integration. It adds "Paste from ClipDrop" to the Windows
# right-click menu and listens for when the user selects it.
#
# It works in two ways:
#   1. REGISTRY  — adds the option to File Explorer & Desktop
#   2. HOTKEY    — Ctrl+Shift+V triggers the popup from anywhere
#
# Both methods open the same dropdown popup at the cursor.
# ============================================================

import winreg
import os
import sys
import threading
import tempfile
import time
import keyboard   # Global hotkey listener
import pyautogui
from dropdown_popup import DropdownPopup


# ---- Registry key paths ----
# These are the locations in the Windows Registry where we add our menu item.
# Think of the Registry like a giant settings book for Windows.

# Adds to right-click on files and the desktop background
REG_PATHS = [
    r"*\shell\ClipDrop",                          # Right-click on any file
    r"Directory\shell\ClipDrop",                  # Right-click on any folder
    r"Directory\Background\shell\ClipDrop",       # Right-click on desktop/folder background
]

# The command Windows runs when "Paste from ClipDrop" is clicked
# It writes a signal file that our running app detects
TRIGGER_SCRIPT = os.path.join(
    os.path.dirname(os.path.abspath(__file__)),
    "trigger_popup.py"
)

# A temporary file used as a signal between the registry command
# and the running ClipDrop app
SIGNAL_FILE = os.path.join(tempfile.gettempdir(), "clipdrop_trigger.signal")

# The hotkey that also opens the popup (works in any app)
HOTKEY = "ctrl+shift+v"


class ContextMenu:

    def __init__(self, history_manager):
        self.history = history_manager
        self.popup = DropdownPopup(history_manager)
        self.running = False


    def setup(self):
        """
        Sets up both context menu integration methods:
        1. Registers ClipDrop into the Windows right-click menu via Registry
        2. Sets up a global hotkey (Ctrl+Shift+V)
        3. Starts listening for triggers from both methods
        """
        self._register_in_registry()
        self._create_trigger_script()
        self._setup_hotkey()

        # Start listening for registry-triggered signals in the background
        self.running = True
        signal_thread = threading.Thread(
            target=self._listen_for_signal,
            daemon=True
        )
        signal_thread.start()

        print(f"Context menu ready. Hotkey: {HOTKEY}")


    def teardown(self):
        """
        Removes ClipDrop from the Windows Registry when the app closes.
        This keeps the right-click menu clean after ClipDrop quits.
        """
        self.running = False
        self._remove_from_registry()
        keyboard.remove_hotkey(HOTKEY)
        print("Context menu removed.")


    # ============================================================
    # METHOD 1 — WINDOWS REGISTRY
    # ============================================================

    def _register_in_registry(self):
        """
        Writes entries into the Windows Registry to add
        "Paste from ClipDrop" to the right-click context menu.

        Each registry path gets two things:
          - A display name ("Paste from ClipDrop")
          - A command to run when clicked (our trigger script)
        """
        command = f'"{sys.executable}" "{TRIGGER_SCRIPT}"'

        for reg_path in REG_PATHS:
            try:
                # Open or create the registry key for ClipDrop
                key = winreg.CreateKeyEx(
                    winreg.HKEY_CLASSES_ROOT,
                    reg_path,
                    0,
                    winreg.KEY_SET_VALUE | winreg.KEY_CREATE_SUB_KEY
                )

                # Set the display name shown in the right-click menu
                winreg.SetValueEx(key, "", 0, winreg.REG_SZ, "Paste from ClipDrop")

                # Set the icon (uses Python's icon for now)
                winreg.SetValueEx(key, "Icon", 0, winreg.REG_SZ, sys.executable)

                winreg.CloseKey(key)

                # Create the "command" sub-key with the actual command to run
                cmd_key = winreg.CreateKeyEx(
                    winreg.HKEY_CLASSES_ROOT,
                    reg_path + r"\command",
                    0,
                    winreg.KEY_SET_VALUE
                )
                winreg.SetValueEx(cmd_key, "", 0, winreg.REG_SZ, command)
                winreg.CloseKey(cmd_key)

                print(f"Registered: {reg_path}")

            except PermissionError:
                # Writing to HKEY_CLASSES_ROOT requires admin privileges
                # If we don't have them, try the user-level registry instead
                self._register_user_level(reg_path, command)

            except Exception as e:
                print(f"Registry error for {reg_path}: {e}")


    def _register_user_level(self, reg_path, command):
        """
        Fallback: registers in the current user's registry
        instead of the system-wide registry.
        This doesn't require admin privileges.
        """
        try:
            user_path = r"Software\Classes\\" + reg_path
            key = winreg.CreateKeyEx(
                winreg.HKEY_CURRENT_USER,
                user_path,
                0,
                winreg.KEY_SET_VALUE | winreg.KEY_CREATE_SUB_KEY
            )
            winreg.SetValueEx(key, "", 0, winreg.REG_SZ, "Paste from ClipDrop")
            winreg.CloseKey(key)

            cmd_key = winreg.CreateKeyEx(
                winreg.HKEY_CURRENT_USER,
                user_path + r"\command",
                0,
                winreg.KEY_SET_VALUE
            )
            winreg.SetValueEx(cmd_key, "", 0, winreg.REG_SZ, command)
            winreg.CloseKey(cmd_key)

            print(f"Registered (user level): {reg_path}")

        except Exception as e:
            print(f"User-level registry error: {e}")


    def _remove_from_registry(self):
        """
        Removes all ClipDrop entries from the Windows Registry.
        Called when the app quits to keep things clean.
        """
        for reg_path in REG_PATHS:
            for root in [winreg.HKEY_CLASSES_ROOT, winreg.HKEY_CURRENT_USER]:
                try:
                    path = reg_path if root == winreg.HKEY_CLASSES_ROOT \
                        else r"Software\Classes\\" + reg_path

                    winreg.DeleteKey(root, path + r"\command")
                    winreg.DeleteKey(root, path)
                except Exception:
                    pass  # Key might not exist — that's fine


    # ============================================================
    # METHOD 2 — GLOBAL HOTKEY (Ctrl+Shift+V)
    # ============================================================

    def _setup_hotkey(self):
        """
        Registers Ctrl+Shift+V as a global hotkey.
        This works in any application — a browser, text editor, game, etc.
        When pressed, it immediately opens the ClipDrop popup at the cursor.
        """
        keyboard.add_hotkey(
            HOTKEY,
            self._on_hotkey_triggered,
            suppress=True   # Prevents Ctrl+Shift+V from doing anything else
        )
        print(f"Hotkey registered: {HOTKEY}")


    def _on_hotkey_triggered(self):
        """
        Called instantly when Ctrl+Shift+V is pressed.
        Gets the current mouse position and shows the popup there.
        """
        x, y = pyautogui.position()
        threading.Thread(
            target=self.popup.show,
            args=(x, y),
            daemon=True
        ).start()


    # ============================================================
    # SIGNAL FILE (IPC — how the registry trigger talks to the app)
    # ============================================================

    def _create_trigger_script(self):
        """
        Creates a tiny Python script called trigger_popup.py.
        When the user clicks "Paste from ClipDrop" in the right-click menu,
        Windows runs this script. The script writes a signal file that
        tells the running ClipDrop app to open the popup.

        Why a separate script?
        The registry can only run a command — it can't directly call
        a function inside our running app. So we use a signal file
        as a messenger between the two.
        """
        script_content = f'''
import tempfile
import os
import pyautogui

# Write a signal file with the current cursor position
signal_file = r"{SIGNAL_FILE}"
x, y = pyautogui.position()

with open(signal_file, "w") as f:
    f.write(f"{{x}},{{y}}")
'''
        with open(TRIGGER_SCRIPT, "w") as f:
            f.write(script_content)

        print("Trigger script created.")


    def _listen_for_signal(self):
        """
        Runs continuously in the background, checking every 0.3 seconds
        for the signal file that trigger_popup.py creates.

        When found:
        1. Reads the cursor position from the file
        2. Deletes the file (so it doesn't trigger again)
        3. Opens the popup at that position
        """
        while self.running:
            if os.path.exists(SIGNAL_FILE):
                try:
                    # Read cursor position from the signal file
                    with open(SIGNAL_FILE, "r") as f:
                        coords = f.read().strip()

                    # Delete the signal file immediately
                    os.remove(SIGNAL_FILE)

                    # Parse the x,y coordinates
                    x, y = map(int, coords.split(","))

                    # Open the popup at that position
                    threading.Thread(
                        target=self.popup.show,
                        args=(x, y),
                        daemon=True
                    ).start()

                except Exception as e:
                    print(f"Signal error: {e}")

            time.sleep(0.3)  # Check every 0.3 seconds
