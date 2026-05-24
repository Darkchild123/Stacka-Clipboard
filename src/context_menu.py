# ============================================================
# ClipDrop - context_menu.py
# ============================================================
# Handles all right-click integration for ClipDrop.
#
# HOW IT WORKS:
#   A low-level Windows mouse hook detects every right-click
#   system-wide — in any app, browser, text editor, HTML form,
#   or anywhere else on Windows.
#
#   When a right-click is detected, a small floating button
#   "📋 Paste from ClipDrop" appears near the cursor.
#   The native right-click menu still opens as normal.
#   Clicking our button opens the ClipDrop popup.
#   The button disappears automatically after 3 seconds.
#
#   A global hotkey Ctrl+Shift+V also works as a backup trigger.
# ============================================================

import ctypes
import ctypes.wintypes as wintypes
import threading
import time
import tkinter as tk
import keyboard
import pyautogui
import winreg
import os
import sys


# ---- Windows API constants ----
WH_MOUSE_LL  = 14          # Low-level mouse hook ID
WM_RBUTTONUP = 0x0205      # Right mouse button released
WM_QUIT      = 0x0012      # Quit message for the hook thread

# ---- Hotkey ----
HOTKEY = "ctrl+shift+v"

# ---- Registry paths (Desktop and File Explorer) ----
REG_PATHS = [
    r"*\shell\ClipDrop",
    r"Directory\shell\ClipDrop",
    r"Directory\Background\shell\ClipDrop",
]

# ---- Overlay appearance ----
OVERLAY_COLOURS = {
    "bg":     "#4f46e5",   # Indigo button background
    "hover":  "#6366f1",   # Lighter on hover
    "text":   "#ffffff",   # White text
    "shadow": "#1e1e2e",   # Dark border
}


class ContextMenu:

    def __init__(self, history_manager, popup, root):
        self.history  = history_manager
        self.popup    = popup    # Shared DropdownPopup
        self.root     = root     # Shared tkinter root
        self.running  = False

        # The floating overlay button (a Toplevel window)
        self.overlay  = None
        self.overlay_timer = None   # Auto-hide timer

        # Windows hook handle — needed to uninstall the hook later
        self.hook_id  = None
        self.hook_thread_id = None  # Thread ID of the hook thread


    # ============================================================
    # SETUP & TEARDOWN
    # ============================================================

    def setup(self):
        """
        Sets up all right-click integration:
        1. Registry entries for Desktop and File Explorer
        2. Global hotkey Ctrl+Shift+V
        3. Low-level mouse hook for all other apps
        """
        self.running = True
        self._build_overlay()           # Build the floating button (hidden)
        self._register_in_registry()    # Add to Desktop/Explorer right-click
        self._setup_hotkey()            # Register Ctrl+Shift+V
        self._install_mouse_hook()      # Start the global mouse hook


    def teardown(self):
        """Cleans up everything when ClipDrop quits."""
        self.running = False
        self._uninstall_mouse_hook()
        self._remove_from_registry()
        try:
            keyboard.remove_hotkey(HOTKEY)
        except Exception:
            pass
        print("Context menu removed.")


    # ============================================================
    # FLOATING OVERLAY BUTTON
    # ============================================================

    def _build_overlay(self):
        """
        Builds the floating "📋 Paste from ClipDrop" button.
        It is created once and hidden — shown/hidden as needed.
        Uses root.after() to run on the main thread safely.
        """
        self.root.after(0, self._create_overlay_window)


    def _create_overlay_window(self):
        """Creates the actual overlay Toplevel window."""
        self.overlay = tk.Toplevel(self.root)
        self.overlay.overrideredirect(True)     # No title bar
        self.overlay.attributes("-topmost", True)
        self.overlay.attributes("-alpha", 0.95) # Slightly transparent
        self.overlay.configure(bg=OVERLAY_COLOURS["shadow"])
        self.overlay.withdraw()                 # Hidden until right-click

        # The clickable button label
        self.overlay_btn = tk.Label(
            self.overlay,
            text="📋  Paste from ClipDrop",
            bg=OVERLAY_COLOURS["bg"],
            fg=OVERLAY_COLOURS["text"],
            font=("Segoe UI", 10, "bold"),
            padx=14,
            pady=8,
            cursor="hand2"
        )
        self.overlay_btn.pack(padx=1, pady=1)

        # Hover effects
        self.overlay_btn.bind("<Enter>",
            lambda e: self.overlay_btn.configure(bg=OVERLAY_COLOURS["hover"]))
        self.overlay_btn.bind("<Leave>",
            lambda e: self.overlay_btn.configure(bg=OVERLAY_COLOURS["bg"]))

        # Click to open ClipDrop popup
        self.overlay_btn.bind("<Button-1>", self._on_overlay_clicked)

        # Hide if user clicks anywhere else
        self.overlay.bind("<FocusOut>", lambda e: self._hide_overlay())


    def _show_overlay(self, x, y):
        """
        Shows the floating button near the right-click position.
        Schedules via root.after() to run on the main thread.
        """
        self.root.after(0, lambda: self._do_show_overlay(x, y))


    def _do_show_overlay(self, x, y):
        """Actually shows the overlay — runs on main thread."""
        if not self.overlay:
            return

        # Cancel any existing auto-hide timer
        if self.overlay_timer:
            self.root.after_cancel(self.overlay_timer)
            self.overlay_timer = None

        # Position the button just above and to the right of the cursor
        offset_x = 10
        offset_y = -50

        screen_w = self.overlay.winfo_screenwidth()
        screen_h = self.overlay.winfo_screenheight()

        # Measure button size
        self.overlay.update_idletasks()
        btn_w = self.overlay.winfo_reqwidth()
        btn_h = self.overlay.winfo_reqheight()

        # Keep it on screen
        pos_x = min(x + offset_x, screen_w - btn_w - 10)
        pos_y = max(y + offset_y, 10)

        self.overlay.geometry(f"+{pos_x}+{pos_y}")
        self.overlay.deiconify()
        self.overlay.lift()

        # Auto-hide after 3 seconds if not clicked
        self.overlay_timer = self.root.after(3000, self._hide_overlay)


    def _hide_overlay(self):
        """Hides the floating button."""
        if self.overlay:
            try:
                self.overlay.withdraw()
            except Exception:
                pass
        if self.overlay_timer:
            try:
                self.root.after_cancel(self.overlay_timer)
            except Exception:
                pass
            self.overlay_timer = None


    def _on_overlay_clicked(self, event):
        """
        Called when the user clicks the floating button.
        Hides the overlay and opens the ClipDrop popup.
        """
        self._hide_overlay()
        x, y = pyautogui.position()
        self.popup.show(x, y)


    # ============================================================
    # LOW-LEVEL MOUSE HOOK
    # ============================================================

    def _install_mouse_hook(self):
        """
        Installs a Windows low-level mouse hook (WH_MOUSE_LL).
        This runs in a dedicated thread with its own message pump
        so it can detect mouse events system-wide in any application.
        """
        hook_thread = threading.Thread(
            target=self._run_hook_loop,
            daemon=True
        )
        hook_thread.start()
        print("Mouse hook installed.")


    def _run_hook_loop(self):
        """
        Runs on a dedicated background thread.
        Installs the WH_MOUSE_LL hook and runs a Windows message pump.

        IMPORTANT: We must explicitly declare argtypes and restype for
        every Windows API call involving pointers. On 64-bit Windows,
        pointer values are 64-bit integers. Without type declarations,
        ctypes defaults to 32-bit and overflows — causing the crash.
        """
        # Store this thread's ID so we can post WM_QUIT to it later
        self.hook_thread_id = ctypes.windll.kernel32.GetCurrentThreadId()

        # --- Set up Windows API function signatures ---
        # This tells ctypes exactly what types each function takes and returns
        user32 = ctypes.windll.user32

        # Define the hook callback type
        # c_long return, c_int + WPARAM + LPARAM arguments
        HOOKPROC = ctypes.WINFUNCTYPE(
            ctypes.c_long,
            ctypes.c_int,
            wintypes.WPARAM,
            wintypes.LPARAM
        )

        # Declare SetWindowsHookExW types
        user32.SetWindowsHookExW.restype  = ctypes.c_void_p
        user32.SetWindowsHookExW.argtypes = [
            ctypes.c_int,
            HOOKPROC,
            wintypes.HINSTANCE,
            wintypes.DWORD
        ]

        # Declare CallNextHookEx types
        # lParam must be LPARAM (pointer-sized) — this was causing the overflow
        user32.CallNextHookEx.restype  = ctypes.c_long
        user32.CallNextHookEx.argtypes = [
            ctypes.c_void_p,   # hhk (hook handle)
            ctypes.c_int,      # nCode
            wintypes.WPARAM,   # wParam
            wintypes.LPARAM    # lParam — pointer-sized, handles 64-bit correctly
        ]

        # Declare UnhookWindowsHookEx types
        user32.UnhookWindowsHookEx.restype  = wintypes.BOOL
        user32.UnhookWindowsHookEx.argtypes = [ctypes.c_void_p]

        # Declare GetMessageW types
        user32.GetMessageW.restype  = wintypes.BOOL
        user32.GetMessageW.argtypes = [
            ctypes.POINTER(wintypes.MSG),
            wintypes.HWND,
            wintypes.UINT,
            wintypes.UINT
        ]

        # Define the MSLLHOOKSTRUCT — mouse event data Windows sends us
        class MSLLHOOKSTRUCT(ctypes.Structure):
            _fields_ = [
                ("pt",          wintypes.POINT),
                ("mouseData",   wintypes.DWORD),
                ("flags",       wintypes.DWORD),
                ("time",        wintypes.DWORD),
                ("dwExtraInfo", ctypes.POINTER(wintypes.ULONG)),
            ]

        def hook_proc(nCode, wParam, lParam):
            """
            Called by Windows for every mouse event system-wide.
            nCode  — whether we should process this event (>= 0 = yes)
            wParam — the mouse event type
            lParam — pointer to MSLLHOOKSTRUCT with position data
            """
            try:
                if nCode >= 0 and wParam == WM_RBUTTONUP:
                    ms = ctypes.cast(
                        lParam,
                        ctypes.POINTER(MSLLHOOKSTRUCT)
                    ).contents
                    x = ms.pt.x
                    y = ms.pt.y
                    self._show_overlay(x, y)
            except Exception as e:
                print(f"Hook proc error: {e}")

            # Always pass the event on — never block native right-click
            return user32.CallNextHookEx(self.hook_id, nCode, wParam, lParam)

        # Keep a reference to the callback — prevents Python garbage collecting it
        self._hook_proc_ref = HOOKPROC(hook_proc)

        # Install the hook system-wide
        self.hook_id = user32.SetWindowsHookExW(
            WH_MOUSE_LL,
            self._hook_proc_ref,
            None,
            0       # 0 = monitor all threads system-wide
        )

        if not self.hook_id:
            print("Failed to install mouse hook.")
            return

        print("Mouse hook running.")

        # Message pump — Windows requires this to deliver hook events
        msg = wintypes.MSG()
        while self.running:
            result = user32.GetMessageW(ctypes.byref(msg), None, 0, 0)
            if result <= 0:
                break
            ctypes.windll.user32.TranslateMessage(ctypes.byref(msg))
            ctypes.windll.user32.DispatchMessageW(ctypes.byref(msg))

        # Clean up the hook when done
        if self.hook_id:
            user32.UnhookWindowsHookEx(self.hook_id)
            self.hook_id = None
            print("Mouse hook removed.")


    def _uninstall_mouse_hook(self):
        """
        Stops the message pump loop by posting WM_QUIT
        to the hook thread, causing it to exit cleanly.
        """
        if self.hook_thread_id:
            ctypes.windll.user32.PostThreadMessageW(
                self.hook_thread_id, WM_QUIT, 0, 0
            )


    # ============================================================
    # GLOBAL HOTKEY
    # ============================================================

    def _setup_hotkey(self):
        """
        Registers Ctrl+Shift+V as a global hotkey.
        Works in any application as an alternative trigger.
        """
        try:
            keyboard.add_hotkey(
                HOTKEY,
                self._on_hotkey_triggered,
                suppress=True
            )
            print(f"Hotkey registered: {HOTKEY}")
        except Exception as e:
            print(f"Hotkey error: {e}")


    def _on_hotkey_triggered(self):
        """Opens the popup at the current cursor position."""
        x, y = pyautogui.position()
        self.popup.show(x, y)


    # ============================================================
    # WINDOWS REGISTRY
    # ============================================================

    def _register_in_registry(self):
        """Adds ClipDrop to the Desktop and File Explorer right-click menu."""
        command = f'"{sys.executable}" -c "import tempfile, pyautogui; open(tempfile.gettempdir()+chr(92)+\'clipdrop.signal\',\'w\').write(str(pyautogui.position()))"'

        for reg_path in REG_PATHS:
            try:
                key = winreg.CreateKeyEx(
                    winreg.HKEY_CURRENT_USER,
                    r"Software\Classes\\" + reg_path,
                    0,
                    winreg.KEY_SET_VALUE | winreg.KEY_CREATE_SUB_KEY
                )
                winreg.SetValueEx(key, "", 0, winreg.REG_SZ, "Paste from ClipDrop")
                winreg.SetValueEx(key, "Icon", 0, winreg.REG_SZ, sys.executable)
                winreg.CloseKey(key)

                cmd_key = winreg.CreateKeyEx(
                    winreg.HKEY_CURRENT_USER,
                    r"Software\Classes\\" + reg_path + r"\command",
                    0,
                    winreg.KEY_SET_VALUE
                )
                winreg.SetValueEx(cmd_key, "", 0, winreg.REG_SZ, command)
                winreg.CloseKey(cmd_key)

            except Exception as e:
                print(f"Registry error: {e}")


    def _remove_from_registry(self):
        """Removes all ClipDrop registry entries on quit."""
        for reg_path in REG_PATHS:
            try:
                winreg.DeleteKey(
                    winreg.HKEY_CURRENT_USER,
                    r"Software\Classes\\" + reg_path + r"\command"
                )
                winreg.DeleteKey(
                    winreg.HKEY_CURRENT_USER,
                    r"Software\Classes\\" + reg_path
                )
            except Exception:
                pass
