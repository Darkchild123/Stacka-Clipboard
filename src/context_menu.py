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
import win32gui
import win32process
import psutil


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

# ---- Apps where the overlay should NOT appear ----
# Windows Explorer (file browser) is excluded because the overlay
# is intrusive when copying/moving files. The hotkey still works there.
EXCLUDED_PROCESSES = {
    "explorer.exe",   # Windows Explorer file browser
}

# ---- Window classes that identify a file browser window ----
# explorer.exe also powers the Desktop — we only exclude the file browser
EXCLUDED_WINDOW_CLASSES = {
    "CabinetWClass",    # File Explorer window
    "ExplorerWClass",   # Older Explorer window
    "WorkerW",          # Desktop background
}

# ---- Apps where the overlay SHOULD appear ----
# Any app not in the excluded list will show the overlay.
# This covers all text editors, browsers, HTML forms, and apps.

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
        4. Signal file watcher for registry-triggered popup
        """
        self.running = True
        self._build_overlay()           # Build the floating button (hidden)
        self._register_in_registry()    # Add to Desktop/Explorer right-click
        self._setup_hotkey()            # Register Ctrl+Shift+V
        self._install_mouse_hook()      # Start the global mouse hook
        threading.Thread(               # Watch for registry signal file
            target=self._watch_signal_file, daemon=True).start()


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
        # The overlay auto-hides after 3 seconds via the timer in _do_show_overlay().
        # No FocusOut binding — the overlay intentionally never takes focus,
        # so focus-based hiding would never fire and could cause odd behaviour.


    def _should_show_overlay(self):
        """
        Checks whether the overlay button should appear.
        Returns False for Windows Explorer file browser windows
        where the button would be intrusive during file operations.
        Returns True for all other apps — text editors, browsers,
        HTML forms, Office apps, terminals, etc.
        """
        try:
            hwnd = win32gui.GetForegroundWindow()
            window_class = win32gui.GetClassName(hwnd)

            # Check window class — excludes file browser windows
            if window_class in EXCLUDED_WINDOW_CLASSES:
                return False

            # Check process name
            _, pid = win32process.GetWindowThreadProcessId(hwnd)
            process = psutil.Process(pid)
            process_name = process.name().lower()

            if process_name in EXCLUDED_PROCESSES:
                # explorer.exe can be the taskbar or Desktop too —
                # only exclude it if the window class is a file browser
                if window_class in EXCLUDED_WINDOW_CLASSES:
                    return False

        except Exception:
            pass  # If detection fails, default to showing the overlay

        return True


    def _show_overlay(self, x, y):
        """
        Shows the floating button near the right-click position.
        First checks whether the current app should show the overlay.

        The native context menu search runs entirely on a background thread
        so we can retry without freezing tkinter.  Only the final UI update
        is scheduled back onto the main thread.
        """
        if not self._should_show_overlay():
            return

        def find_and_show():
            """
            Searches for the native context menu rect with retry logic.
            Different apps render their menus at different speeds — some
            take longer than 120 ms.  We poll up to ~300 ms total.
            """
            menu_rect = None
            for wait in (0.10, 0.05, 0.05, 0.05, 0.05):
                time.sleep(wait)
                menu_rect = self._find_context_menu_rect()
                if menu_rect:
                    break

            # Hand off to the main thread for the UI update
            self.root.after(0, lambda: self._do_show_overlay(x, y, menu_rect))

        threading.Thread(target=find_and_show, daemon=True).start()


    def _find_context_menu_rect(self):
        """
        Searches for the native Windows context menu window.
        Context menus always use the window class '#32768'.
        Returns (left, top, right, bottom) or None if not found.
        """
        found = []

        def enum_callback(hwnd, _):
            try:
                if win32gui.IsWindowVisible(hwnd):
                    class_name = win32gui.GetClassName(hwnd)
                    if class_name == "#32768":
                        rect = win32gui.GetWindowRect(hwnd)
                        # Only count it if it has a real size
                        if rect[2] - rect[0] > 10 and rect[3] - rect[1] > 10:
                            found.append(rect)
            except Exception:
                pass

        try:
            win32gui.EnumWindows(enum_callback, None)
        except Exception:
            pass

        return found[0] if found else None


    def _best_position(self, menu_rect, btn_w, btn_h, screen_w, screen_h):
        """
        Places the overlay button strictly outside the context menu borders.

        For each of the four directions, this calculates the exact position,
        clamps it to the screen, and then checks whether the clamped result
        actually overlaps the menu.  Directions are tried in order of
        available space; the first one that is genuinely clear wins.

        This handles the common failure case: "below" looks like the best
        direction by score, but screen-edge clamping pulls the button back
        up into the menu.  We detect that and fall through to the next
        direction automatically.
        """
        ml, mt, mr, mb = menu_rect
        PAD  = 10    # Minimum gap between button edge and menu edge
        EDGE = 5     # Minimum distance from screen edge

        def clamp_pos(x, y):
            """Keeps the button fully on screen."""
            x = max(EDGE, min(x, screen_w - btn_w - EDGE))
            y = max(EDGE, min(y, screen_h - btn_h - EDGE))
            return x, y

        def overlaps_menu(x, y):
            """True if the button at (x, y) overlaps the menu rectangle."""
            btn_r = x + btn_w
            btn_b = y + btn_h
            return (x < mr and btn_r > ml and y < mb and btn_b > mt)

        # Available pixels in each direction (screen space minus button minus gap)
        space_above = mt            - EDGE - PAD
        space_below = screen_h - mb - EDGE - PAD
        space_left  = ml            - EDGE - PAD
        space_right = screen_w - mr - EDGE - PAD

        # Each candidate: (score, raw_x, raw_y)
        # raw position is before clamping; score = leftover space after button fits
        candidates = [
            (space_above - btn_h,  ml,              mt - btn_h - PAD),  # above
            (space_below - btn_h,  ml,              mb + PAD),          # below
            (space_left  - btn_w,  ml - btn_w - PAD, mt),              # left
            (space_right - btn_w,  mr + PAD,         mt),              # right
        ]

        # Try directions from most space to least
        candidates.sort(key=lambda c: c[0], reverse=True)

        for score, raw_x, raw_y in candidates:
            x, y = clamp_pos(raw_x, raw_y)
            if not overlaps_menu(x, y):
                return x, y  # First clear position wins

        # Every direction overlaps (extremely tight screen / huge menu).
        # Use the highest-scored direction and accept it as the best we can do.
        _, raw_x, raw_y = candidates[0]
        return clamp_pos(raw_x, raw_y)


    def _do_show_overlay(self, x, y, menu_rect=None):
        """
        Positions and shows the overlay button.

        menu_rect is supplied by the background thread in _show_overlay —
        it has already retried up to ~300 ms to find the native context menu.

        If menu_rect was found: use smart border-based positioning.
        If not found: place the button in a corner well away from the cursor
        so we don't accidentally land on top of the invisible menu.

        NOTE: Do NOT call focus_force() here.
        focus_force() steals focus from the native context menu, causing
        Windows to close it immediately. The button works without focus.
        """
        if not self.overlay:
            return

        # Cancel any existing auto-hide timer
        if self.overlay_timer:
            self.root.after_cancel(self.overlay_timer)
            self.overlay_timer = None

        # Measure our button's dimensions
        self.overlay.update_idletasks()
        btn_w = self.overlay.winfo_reqwidth()
        btn_h = self.overlay.winfo_reqheight()

        screen_w = self.overlay.winfo_screenwidth()
        screen_h = self.overlay.winfo_screenheight()

        if menu_rect:
            # Smart positioning — place in the largest clear space around the menu
            pos_x, pos_y = self._best_position(
                menu_rect, btn_w, btn_h, screen_w, screen_h
            )
        else:
            # Fallback — menu window not detected.
            # Some apps (browsers, HTML forms, custom UI frameworks) render
            # their context menus without using Windows' standard #32768 class,
            # so we can't find the rect directly.
            #
            # Windows' context menu placement follows a predictable rule:
            # the menu always opens AWAY from the nearest screen edge.
            #
            #   cursor in left  half  → menu opens to the RIGHT of cursor
            #   cursor in right half  → menu opens to the LEFT  of cursor
            #   cursor in top   half  → menu opens DOWNWARD from cursor
            #   cursor in bottom half → menu opens UPWARD   from cursor
            #
            # Counter-logic: place our button on the OPPOSITE side of the
            # cursor from where the menu opened — that space is guaranteed
            # to be clear of the menu.
            PAD  = 10
            EDGE = 5

            # Dead zone detection — the centre 20% of the screen in both axes
            # (X: 40%–60%, Y: 40%–60%).  In this region Windows has maximum
            # freedom to open the menu in any direction, so cursor-position
            # prediction is unreliable.  We always place the button LEFT of
            # the cursor here — consistent and out of the way.
            in_dead_zone = (
                screen_w * 0.40 <= x <= screen_w * 0.60 and
                screen_h * 0.40 <= y <= screen_h * 0.60
            )

            if in_dead_zone:
                # Dead zone → always LEFT of cursor
                pos_x = max(EDGE, x - btn_w - PAD)
            elif x < screen_w // 2:
                # Left half → menu opens RIGHT → button goes LEFT of cursor
                pos_x = max(EDGE, x - btn_w - PAD)
            else:
                # Right half → menu opens LEFT → button goes RIGHT of cursor
                pos_x = min(x + PAD, screen_w - btn_w - EDGE)

            # Vertical: opposite side from where menu opened
            if y < screen_h // 2:
                # Menu opens DOWNWARD → button goes ABOVE cursor
                pos_y = max(EDGE, y - btn_h - PAD)
            else:
                # Menu opens UPWARD → button goes BELOW cursor
                pos_y = min(y + PAD, screen_h - btn_h - EDGE)

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
    # REGISTRY SIGNAL FILE WATCHER
    # ============================================================

    def _watch_signal_file(self):
        """
        Watches for the signal file written by the Windows Registry command.

        When the user clicks "Paste from ClipDrop" in the Desktop or
        File Explorer right-click menu, the registry command fires a
        separate pythonw.exe process that writes:
            %TEMP%\\clipdrop.signal
        containing the cursor position at the time of the click.

        This thread polls for that file every 200ms.  When found it:
          1. Reads the cursor position
          2. Deletes the file so it won't trigger again
          3. Opens the ClipDrop popup at that position
        """
        import tempfile
        signal_path = os.path.join(tempfile.gettempdir(), "clipdrop.signal")

        while self.running:
            try:
                if os.path.exists(signal_path):
                    with open(signal_path, "r") as f:
                        content = f.read().strip()
                    os.remove(signal_path)

                    # pyautogui.position() writes "Point(x=1204, y=540)"
                    # Extract the two integers with regex
                    import re
                    nums = re.findall(r"\d+", content)
                    x = int(nums[0])
                    y = int(nums[1])

                    self.popup.show(x, y)
                    print(f"Registry trigger received at ({x}, {y})")

            except Exception as e:
                print(f"Signal file error: {e}")

            time.sleep(0.2)


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

        # Use pythonw.exe instead of python.exe
        # pythonw.exe runs Python silently — no console window appears
        pythonw = sys.executable.replace("python.exe", "pythonw.exe")
        if not os.path.exists(pythonw):
            pythonw = sys.executable  # Fallback if pythonw not found

        command = f'"{pythonw}" -c "import tempfile, pyautogui; open(tempfile.gettempdir()+chr(92)+\'clipdrop.signal\',\'w\').write(str(pyautogui.position()))"'

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
