# ============================================================
# ClipDrop - context_menu.py  (PyQt6 rewrite)
# ============================================================
# Handles all right-click integration for ClipDrop.
#
# A low-level Windows mouse hook detects every right-click
# system-wide. When detected, a small floating button
# "📋 Paste from ClipDrop" appears near the cursor.
# Clicking it opens the ClipDrop popup.
# The button disappears automatically after 3 seconds.
#
# Global hotkey Ctrl+Shift+V also triggers the popup.
# ============================================================

import ctypes
import ctypes.wintypes as wintypes
import threading
import time
import os
import sys
import re
import tempfile

import keyboard
import pyautogui
import winreg
import win32gui
import win32process
import psutil

from PyQt6.QtWidgets import QWidget, QLabel, QHBoxLayout, QApplication, QMessageBox
from PyQt6.QtCore    import Qt, QTimer, QPoint, pyqtSignal, QObject

# ---- Windows API constants ----
WH_MOUSE_LL    = 14
WM_LBUTTONDOWN = 0x0201
WM_RBUTTONDOWN = 0x0204
WM_RBUTTONUP   = 0x0205
WM_MBUTTONDOWN = 0x0207
WM_MBUTTONUP   = 0x0208
WM_XBUTTONDOWN = 0x020B
WM_XBUTTONUP   = 0x020C
WM_QUIT        = 0x0012
VK_CONTROL     = 0x11

# WinEvent hook — fired system-wide when a NATIVE menu opens/closes. Used
# only to hide the overlay button the instant its menu is dismissed (so it
# doesn't linger on the 3 s fallback timer). Does NOT fire for Chromium /
# in-page menus — those keep the timer, by design.
EVENT_SYSTEM_MENUPOPUPSTART = 0x0006
EVENT_SYSTEM_MENUPOPUPEND    = 0x0007
WINEVENT_OUTOFCONTEXT   = 0x0000
WINEVENT_SKIPOWNPROCESS = 0x0002   # ignore our own popup's QMenus

HOTKEY = "ctrl+shift+v"

# ── Configurable shortcuts (canonical table) ─────────────────────────────────
# (settings_key, label shown in the Shortcuts window, default combo)
# The Shortcuts window builds its rows from this list; ContextMenu binds
# every entry at startup. Defaults use plain letters only — named keys
# (Del, Tab…) spell differently between Qt and the keyboard library.
SHORTCUT_DEFS = [
    ("hotkey_open",    "Open ClipDrop popup window",       "ctrl+shift+v"),
    ("hotkey_pause",   "Pause / resume clipboard capture", "ctrl+shift+p"),
    ("hotkey_snippet", "New snippet (blank scratchpad)",   "ctrl+shift+n"),
    ("hotkey_clear",   "Clear all history",                "ctrl+shift+h"),
    ("hotkey_profile", "Switch to next profile",           "ctrl+shift+o"),
]

REG_PATHS = [
    r"*\shell\ClipDrop",
    r"Directory\shell\ClipDrop",
    r"Directory\Background\shell\ClipDrop",
]

EXCLUDED_PROCESSES = {"explorer.exe"}
EXCLUDED_WINDOW_CLASSES = {"CabinetWClass", "ExplorerWClass", "WorkerW"}

OVERLAY_BG    = "#4f46e5"
OVERLAY_HOVER = "#6366f1"


class _OverlaySignals(QObject):
    show_overlay = pyqtSignal(int, int, object)   # x, y, menu_rect or None
    hide_overlay = pyqtSignal()
    hide_popup_if_outside = pyqtSignal(int, int)
    run_action   = pyqtSignal(str)   # settings_key of a hotkey action —
                                     # hotkey callbacks fire on the keyboard
                                     # library's thread; this marshals them
                                     # onto the Qt main thread.
    open_popup_at = pyqtSignal(int, int, bool)   # mouse trigger → open the
                                           # ClipDrop popup at (x, y). bool =
                                           # dismiss a native menu first (only
                                           # double-right-click flashes one).


class OverlayButton(QWidget):
    """The floating '📋 Paste from ClipDrop' button."""

    def __init__(self, on_clicked):
        super().__init__(None,
            Qt.WindowType.FramelessWindowHint |
            Qt.WindowType.WindowStaysOnTopHint |
            Qt.WindowType.Tool)
        self.setAttribute(Qt.WidgetAttribute.WA_ShowWithoutActivating)
        self.on_clicked = on_clicked

        lay = QHBoxLayout(self)
        lay.setContentsMargins(1,1,1,1)

        self._lbl = QLabel("📋  Paste from ClipDrop", self)
        self._lbl.setStyleSheet(
            f"background:{OVERLAY_BG};color:white;"
            "font-family:'Segoe UI';font-size:10pt;font-weight:bold;"
            "padding:8px 14px;border-radius:4px;")
        self._lbl.setCursor(Qt.CursorShape.PointingHandCursor)
        lay.addWidget(self._lbl)

        self.adjustSize()
        self.setWindowOpacity(0.95)
        self.hide()

        # Apply WS_EX_NOACTIVATE after first show
        self._hwnd_set = False

        # Auto-hide timer
        self._timer = QTimer(self)
        self._timer.setSingleShot(True)
        self._timer.timeout.connect(self.hide)

    def _apply_no_activate(self):
        if not self._hwnd_set:
            try:
                import win32con
                hwnd = int(self.winId())
                ex = win32gui.GetWindowLong(hwnd, win32con.GWL_EXSTYLE)
                win32gui.SetWindowLong(hwnd, win32con.GWL_EXSTYLE,
                                       ex | win32con.WS_EX_NOACTIVATE)
                self._hwnd_set = True
            except Exception:
                pass

    def show_at(self, x: int, y: int, menu_rect):
        """Place the button AT the cursor, hugging the context menu's
        border — never covering the menu, never drifting across the
        screen, never on the taskbar.

        Anchor is always the CURSOR (where the user's attention is).
        With a detected menu rect we sit just outside the menu border
        nearest the cursor, vertically aligned with the click. Without
        one we sit beside the cursor on the side the menu won't occupy.
        """
        self._timer.stop()
        # sizeHint() asks the layout for its required size without needing
        # the widget to have been shown before. width()/height() on an
        # unshown widget return 0 and break all positioning calculations.
        self.ensurePolished()
        hint = self.sizeHint()
        w = hint.width()  if hint.width()  > 0 else 200
        h = hint.height() if hint.height() > 0 else 40
        # The screen the CLICK is on, taskbar excluded — primaryScreen()
        # .geometry() put the button on the taskbar / wrong monitor.
        screen = QApplication.screenAt(QPoint(x, y)) or QApplication.primaryScreen()
        g = screen.availableGeometry()

        if menu_rect:
            pos_x, pos_y = self._beside_menu(x, y, menu_rect, w, h, g)
        else:
            pos_x, pos_y = self._beside_cursor(x, y, w, h, g)

        self.move(pos_x, pos_y)
        self.show()
        self._apply_no_activate()
        self.raise_()
        self._timer.start(3000)

    def _beside_menu(self, x, y, menu_rect, w, h, g):
        """Hug the menu border nearest the cursor, at cursor height."""
        ml, mt, mr, mb = menu_rect
        GAP = 8
        by = max(g.top(), min(y - h // 2, g.bottom() - h))

        # Menus open FROM the click point: cursor sits on one vertical
        # border of the menu. Prefer the border the cursor is nearest —
        # that's directly beside the click.
        left_x, right_x = ml - w - GAP, mr + GAP
        order = ([left_x, right_x] if (x - ml) <= (mr - x)
                 else [right_x, left_x])
        for bx in order:
            if g.left() <= bx and bx + w <= g.right():
                return bx, by

        # No room on either side (menu spans the screen) → just outside
        # the top/bottom border nearest the cursor.
        bx = max(g.left(), min(x - w // 2, g.right() - w))
        top_y, bot_y = mt - h - GAP, mb + GAP
        vorder = ([top_y, bot_y] if (y - mt) <= (mb - y)
                  else [bot_y, top_y])
        for vy in vorder:
            if g.top() <= vy and vy + h <= g.bottom():
                return bx, vy

        return self._beside_cursor(x, y, w, h, g)   # pathological fallback

    def _beside_cursor(self, x, y, w, h, g):
        """No menu rect detected: sit beside the cursor on the side the
        menu won't occupy. Windows menus open RIGHTWARD from the click
        when there's room, so the safe side is LEFT of the cursor —
        unless the click is near the right screen edge (menu opens left,
        so we go right). If NEITHER side has room, escape vertically:
        just above the click, since menus open downward from it —
        clamping horizontally instead would land inside the menu."""
        GAP = 12
        MENU_W = 220        # typical context-menu width
        opens_right = (g.right() - x) >= MENU_W
        if opens_right:
            bx = x - w - GAP
            by = y - h // 2
        else:
            bx = x + GAP
            if bx + w <= g.right():
                by = y - h // 2
            else:                     # no room beside — go above the click
                bx = g.right() - w
                by = y - h - GAP
                if by < g.top():      # top-right corner: below instead
                    by = y + GAP
        bx = max(g.left(), min(bx, g.right() - w))
        by = max(g.top(), min(by, g.bottom() - h))
        return bx, by

    def enterEvent(self, e):
        self._lbl.setStyleSheet(self._lbl.styleSheet().replace(OVERLAY_BG, OVERLAY_HOVER))
        super().enterEvent(e)

    def leaveEvent(self, e):
        self._lbl.setStyleSheet(self._lbl.styleSheet().replace(OVERLAY_HOVER, OVERLAY_BG))
        super().leaveEvent(e)

    def mousePressEvent(self, e):
        if e.button() == Qt.MouseButton.LeftButton:
            self._timer.stop()
            self.hide()
            self.on_clicked()
        super().mousePressEvent(e)


class ContextMenu:

    def __init__(self, history_manager, popup, root=None):
        self.history  = history_manager
        self.popup    = popup
        # root is unused in Qt but kept for API compatibility
        self.running  = False
        self.hook_id  = None
        self.hook_thread_id = None
        self._overlay = None
        self._signals = _OverlaySignals()
        self._right_click_target = None
        self._winevent_hook  = None
        self._menu_open_count = 0   # nesting depth of open native menus
        # Mouse-trigger state
        self._last_rdown = 0.0      # ms timestamp of previous right-down
        self._last_rpos  = (0, 0)
        self._swallow_ups = set()   # WM_*BUTTONUP codes to swallow (matches
                                    # a DOWN we already consumed)
        self._rclick_target = None  # foreground window at the trigger click
        self._dbl_ms = 500          # system double-click time (set at hook start)

    # ── Setup / teardown ─────────────────────────────────────────────────────

    def setup(self):
        self.running = True
        # Create overlay directly — we're already on the main thread
        self._create_overlay()
        self._register_in_registry()
        self._setup_hotkey()
        self._install_mouse_hook()
        threading.Thread(target=self._watch_signal_file, daemon=True).start()

    def teardown(self):
        self.running = False
        self._uninstall_mouse_hook()
        self._remove_from_registry()
        for combo in getattr(self, "_hotkeys", {}).values():
            try:
                keyboard.remove_hotkey(combo)
            except Exception:
                pass
        print("Context menu removed.")

    # ── Overlay ───────────────────────────────────────────────────────────────

    def _create_overlay(self):
        self._overlay = OverlayButton(on_clicked=self._on_overlay_clicked)
        # Connect signals to slots (thread-safe cross-thread calls)
        self._signals.show_overlay.connect(self._on_show_overlay)
        self._signals.hide_overlay.connect(self._on_hide_overlay)
        self._signals.hide_popup_if_outside.connect(self._on_hide_popup_if_outside)
        self._signals.run_action.connect(self._dispatch_action)
        self._signals.open_popup_at.connect(self._on_mouse_trigger)

    def _on_show_overlay(self, x, y, menu_rect):
        if self._overlay:
            self._overlay.show_at(x, y, menu_rect)

    def _on_hide_overlay(self):
        if self._overlay:
            self._overlay.hide()

    def _show_overlay(self, x, y):
        try:
            self._right_click_target = win32gui.GetForegroundWindow()
        except Exception:
            self._right_click_target = None
        if not self._should_show_overlay():
            return

        def find_and_show():
            menu_rect = None
            for wait in (0.10, 0.05, 0.05, 0.05, 0.05):
                time.sleep(wait)
                menu_rect = self._find_context_menu_rect(near=(x, y))
                if menu_rect:
                    break
            if menu_rect is None:
                # Tier 3, one shot: in-page menus via UI Automation —
                # by now (~300 ms) the menu is fully rendered.
                menu_rect = self._uia_menu_rect(x, y)
            self._signals.show_overlay.emit(x, y, menu_rect)

        threading.Thread(target=find_and_show, daemon=True).start()

    def _should_show_overlay(self):
        try:
            hwnd = win32gui.GetForegroundWindow()
            wc   = win32gui.GetClassName(hwnd)
            if wc in EXCLUDED_WINDOW_CLASSES:
                return False
            _, pid = win32process.GetWindowThreadProcessId(hwnd)
            proc = psutil.Process(pid)
            if proc.name().lower() in EXCLUDED_PROCESSES and wc in EXCLUDED_WINDOW_CLASSES:
                return False
        except Exception:
            pass
        return True

    def _find_context_menu_rect(self, near=None):
        """Borders (left, top, right, bottom) of the open context menu.

        Tier 1 — native Win32 menus: window class '#32768'. Exact match,
        highest confidence (Explorer, desktop, classic apps).

        Tier 2 — Chromium/Electron menus (Chrome, Edge, VS Code,
        Discord…): real top-level popup HWNDs but with app-specific
        window classes. Identified heuristically: visible WS_POPUP
        window, no caption, menu-like proportions, adjacent to the
        click, owned by the foreground app's process, and not ours.

        NOT findable by any HWND scan: menus that web apps draw INSIDE
        their page (no window of their own) — those fall back to the
        cursor-side guess in OverlayButton._beside_cursor.
        """
        native, popup = [], []
        fg_pid = None
        if near is not None:
            try:
                fg = win32gui.GetForegroundWindow()
                fg_pid = win32process.GetWindowThreadProcessId(fg)[1]
            except Exception:
                pass
        my_pid = os.getpid()

        def cb(hwnd, _):
            try:
                if not win32gui.IsWindowVisible(hwnd):
                    return
                cls  = win32gui.GetClassName(hwnd)
                rect = win32gui.GetWindowRect(hwnd)
                w, h = rect[2] - rect[0], rect[3] - rect[1]

                if cls == "#32768":                    # Tier 1
                    if w > 10 and h > 10:
                        native.append(rect)
                    return

                if near is None:                       # Tier 2 needs the click
                    return
                pid = win32process.GetWindowThreadProcessId(hwnd)[1]
                if pid == my_pid:                      # our own popup/overlay
                    return
                if fg_pid is not None and pid != fg_pid:
                    return                             # not the clicked app
                style = win32gui.GetWindowLong(hwnd, win32con.GWL_STYLE)
                if not (style & win32con.WS_POPUP):
                    return
                if (style & win32con.WS_CAPTION) == win32con.WS_CAPTION:
                    return                             # real window, not a menu
                if not (80 <= w <= 520 and 40 <= h <= 900):
                    return                             # not menu proportions
                # A context menu opens FROM the click — the click point
                # must touch (or nearly touch) its frame.
                x, y = near
                M = 32
                if not (rect[0] - M <= x <= rect[2] + M and
                        rect[1] - M <= y <= rect[3] + M):
                    return
                popup.append(rect)
            except Exception:
                pass

        try:
            win32gui.EnumWindows(cb, None)
        except Exception:
            pass
        if native:
            return native[0]
        if popup:
            # Smallest candidate — submenu/tooltip windows are filtered by
            # proportions above; the menu is the tightest fit to the click
            return min(popup, key=lambda r: (r[2]-r[0]) * (r[3]-r[1]))
        return None

    def _uia_menu_rect(self, x, y):
        """Tier 3 — menus drawn INSIDE an app's window (web pages and
        Electron apps: Claude, Slack, Teams…). No HWND exists for those,
        so no window scan can find them. Instead, ask the app's UI
        Automation (accessibility) tree for an open menu element and use
        its bounding rectangle.

        Caveats, by design:
        - Works only when the app exposes menus to accessibility.
          Chromium/Electron do — but their accessibility layer wakes
          LAZILY on the first UIA query, so the first right-click in an
          app may miss while later ones hit.
        - One shot only, after the fast HWND tiers missed (UIA tree
          walks cost tens of milliseconds).
        """
        try:
            import comtypes
            import comtypes.client
            comtypes.CoInitialize()   # fresh thread per detection run
            try:
                comtypes.client.GetModule("UIAutomationCore.dll")
                from comtypes.gen.UIAutomationClient import (
                    CUIAutomation, IUIAutomation)
                uia = comtypes.client.CreateObject(
                    CUIAutomation, interface=IUIAutomation)
                fg = win32gui.GetForegroundWindow()
                if not fg:
                    return None
                root = uia.ElementFromHandle(fg)
                # UIA_ControlTypePropertyId (30003) == Menu (50009).
                # FindAll, not FindFirst: an app can have a menu BAR in
                # its tree too — we want the menu AT the click.
                cond  = uia.CreatePropertyCondition(30003, 50009)
                found = root.FindAll(4, cond)   # TreeScope_Descendants
                if found is None:
                    return None
                M = 40                          # menu must touch the click
                best = None
                for i in range(found.Length):
                    r = found.GetElement(i).CurrentBoundingRectangle
                    l, t, rr, b = (int(r.left), int(r.top),
                                   int(r.right), int(r.bottom))
                    w, h = rr - l, b - t
                    if not (60 <= w <= 700 and 30 <= h <= 1000):
                        continue                # not menu proportions
                    if not (l - M <= x <= rr + M and t - M <= y <= b + M):
                        continue                # a menubar or distant menu
                    area = w * h
                    if best is None or area < best[0]:
                        best = (area, (l, t, rr, b))
                return best[1] if best else None
            finally:
                comtypes.CoUninitialize()
        except Exception:
            return None   # comtypes missing / app exposes nothing — fall back

    def _on_overlay_clicked(self):
        self.popup._paste_target = self._right_click_target
        x, y = pyautogui.position()
        self.popup.show(x, y)

    def _on_mouse_trigger(self, x, y, dismiss_menu):
        """A mouse-gesture trigger fired (main thread). The paste target
        was captured on the click, before any menu stole focus."""
        try:
            self.popup._paste_target = (self._rclick_target
                                        or win32gui.GetForegroundWindow())
        except Exception:
            self.popup._paste_target = None
        if dismiss_menu:
            try:
                keyboard.send("esc")   # close the menu double-right flashed
            except Exception:
                pass
        self.popup.show(x, y)

    def _handle_trigger(self, mode, wParam, lParam, MSLLHOOKSTRUCT, user32):
        """Per-mode mouse-trigger dispatch (hook thread). Returns True to
        SWALLOW the event (stop it reaching the app). Runs only on real
        button events, never on moves."""
        def pt():
            ms = ctypes.cast(lParam, ctypes.POINTER(MSLLHOOKSTRUCT)).contents
            return ms.pt.x, ms.pt.y

        def capture_target():
            try:
                self._rclick_target = win32gui.GetForegroundWindow()
            except Exception:
                self._rclick_target = None

        if mode == "double_right":
            if wParam == WM_RBUTTONDOWN:
                x, y = pt()
                now = time.time() * 1000.0
                if (now - self._last_rdown <= self._dbl_ms
                        and abs(x - self._last_rpos[0]) <= 8
                        and abs(y - self._last_rpos[1]) <= 8):
                    # Second quick click → open ClipDrop; swallow it so the
                    # app's menu doesn't re-toggle under our popup.
                    self._last_rdown = 0.0
                    self._swallow_ups.add(WM_RBUTTONUP)
                    self._signals.open_popup_at.emit(x, y, True)   # esc menu
                    return True
                self._last_rdown = now
                self._last_rpos  = (x, y)
                capture_target()      # first click passes through (native menu)
            return False

        if mode == "button":
            if wParam == WM_RBUTTONUP:
                x, y = pt()
                self._show_overlay(x, y)
            return False

        if mode == "middle":
            if wParam == WM_MBUTTONDOWN:
                x, y = pt(); capture_target()
                self._swallow_ups.add(WM_MBUTTONUP)
                self._signals.open_popup_at.emit(x, y, False)
                return True
            return False

        if mode == "side":
            if wParam == WM_XBUTTONDOWN:
                x, y = pt(); capture_target()
                self._swallow_ups.add(WM_XBUTTONUP)
                self._signals.open_popup_at.emit(x, y, False)
                return True
            return False

        if mode == "ctrl_right":
            if wParam == WM_RBUTTONDOWN and (
                    user32.GetAsyncKeyState(VK_CONTROL) & 0x8000):
                # Ctrl+right-click → suppress the native menu entirely
                # (swallow both down and up) and open ClipDrop. No flash.
                x, y = pt(); capture_target()
                self._swallow_ups.add(WM_RBUTTONUP)
                self._signals.open_popup_at.emit(x, y, False)
                return True
            return False

        return False   # "hotkey" mode — no mouse trigger

    # ── Hide popup on outside click ───────────────────────────────────────────

    def _on_hide_popup_if_outside(self, click_x, click_y):
        win = getattr(self.popup, "_popup", None)
        if not win or not win.isVisible():
            return
        try:
            # Use Windows API to find which window was clicked.
            # The mouse hook gives raw physical pixel coordinates; Qt's
            # win.x()/win.y() are logical coordinates that don't match on
            # HiDPI screens. WindowFromPoint works in physical pixels — the
            # same space as the hook — so it's always accurate regardless of DPI.
            #
            # ClipDrop UI spans MANY top-level windows: the main popup, the
            # file side panel, right-click QMenus ("Send to profile…"), the
            # profile-switcher QMenu… Enumerating them individually kept
            # missing one (side panel, then menus — each a "popup closes
            # unexpectedly" bug). The robust test: if the clicked window
            # belongs to THIS PROCESS, it is ClipDrop UI — never hide.
            clicked_hwnd = win32gui.WindowFromPoint((click_x, click_y))
            if clicked_hwnd:
                _tid, pid = win32process.GetWindowThreadProcessId(clicked_hwnd)
                if pid == os.getpid():
                    return  # Click is inside ClipDrop UI — do not hide
            self.popup.hide()
        except Exception:
            pass

    # ── Registry signal file watcher ──────────────────────────────────────────

    def _watch_signal_file(self):
        signal_path = os.path.join(tempfile.gettempdir(), "clipdrop.signal")
        while self.running:
            try:
                if os.path.exists(signal_path):
                    with open(signal_path, "r") as f:
                        content = f.read().strip()
                    os.remove(signal_path)
                    nums = re.findall(r"\d+", content)
                    x, y = int(nums[0]), int(nums[1])
                    try:
                        self.popup._paste_target = win32gui.GetForegroundWindow()
                    except Exception:
                        self.popup._paste_target = None
                    self.popup.show(x, y)
                    print(f"Registry trigger received at ({x}, {y})")
            except Exception as e:
                print(f"Signal file error: {e}")
            time.sleep(0.2)

    # ── Mouse hook ────────────────────────────────────────────────────────────

    def _install_mouse_hook(self):
        hook_thread = threading.Thread(target=self._run_hook_loop, daemon=True)
        hook_thread.start()
        print("Mouse hook installed.")

    def _run_hook_loop(self):
        self.hook_thread_id = ctypes.windll.kernel32.GetCurrentThreadId()
        user32 = ctypes.windll.user32
        # Respect the user's system double-click speed for the double-
        # right-click gesture (floor at 300 ms so it's always achievable).
        try:
            self._dbl_ms = max(300, user32.GetDoubleClickTime())
        except Exception:
            self._dbl_ms = 500
        user32.GetAsyncKeyState.restype = ctypes.c_short   # for Ctrl+right

        HOOKPROC = ctypes.WINFUNCTYPE(ctypes.c_long, ctypes.c_int, wintypes.WPARAM, wintypes.LPARAM)
        user32.SetWindowsHookExW.restype  = ctypes.c_void_p
        user32.SetWindowsHookExW.argtypes = [ctypes.c_int, HOOKPROC, wintypes.HINSTANCE, wintypes.DWORD]
        user32.CallNextHookEx.restype  = ctypes.c_long
        user32.CallNextHookEx.argtypes = [ctypes.c_void_p, ctypes.c_int, wintypes.WPARAM, wintypes.LPARAM]
        user32.UnhookWindowsHookEx.restype  = wintypes.BOOL
        user32.UnhookWindowsHookEx.argtypes = [ctypes.c_void_p]
        user32.GetMessageW.restype  = wintypes.BOOL
        user32.GetMessageW.argtypes = [ctypes.POINTER(wintypes.MSG), wintypes.HWND, wintypes.UINT, wintypes.UINT]

        class MSLLHOOKSTRUCT(ctypes.Structure):
            _fields_ = [("pt", wintypes.POINT), ("mouseData", wintypes.DWORD),
                        ("flags", wintypes.DWORD), ("time", wintypes.DWORD),
                        ("dwExtraInfo", ctypes.POINTER(wintypes.ULONG))]

        # Imported here (not at module top) purely for the hook's benefit
        from dropdown_popup import _DRAG_STATE

        def hook_proc(nCode, wParam, lParam):
            # ── HOT PATH ──  This runs for EVERY mouse event on the
            # system, including every mouse-move. Moves must bail on pure
            # int compares — per-move Python work adds system-wide cursor
            # latency (it once made drag-and-drop lag and stall OLE drops).
            if nCode >= 0 and not _DRAG_STATE["active"]:
                if wParam == WM_LBUTTONDOWN:
                    try:
                        ms = ctypes.cast(lParam, ctypes.POINTER(MSLLHOOKSTRUCT)).contents
                        self._signals.hide_popup_if_outside.emit(ms.pt.x, ms.pt.y)
                    except Exception as e:
                        print(f"Hook proc error: {e}")
                elif (wParam == WM_RBUTTONDOWN or wParam == WM_RBUTTONUP
                      or wParam == WM_MBUTTONDOWN or wParam == WM_MBUTTONUP
                      or wParam == WM_XBUTTONDOWN or wParam == WM_XBUTTONUP):
                    # Swallow the release matching a DOWN we already
                    # consumed (keeps the click balanced for the app).
                    if wParam in self._swallow_ups:
                        self._swallow_ups.discard(wParam)
                        return 1
                    # Settings read only on real button events, never moves.
                    try:
                        mode = self.history.settings.get("trigger_mode", "double_right")
                    except Exception:
                        mode = "double_right"
                    try:
                        if self._handle_trigger(mode, wParam, lParam,
                                                MSLLHOOKSTRUCT, user32):
                            return 1   # consumed the click
                    except Exception as e:
                        print(f"Hook proc error: {e}")
            return user32.CallNextHookEx(self.hook_id, nCode, wParam, lParam)

        self._hook_proc_ref = HOOKPROC(hook_proc)
        self.hook_id = user32.SetWindowsHookExW(WH_MOUSE_LL, self._hook_proc_ref, None, 0)
        if not self.hook_id:
            print("Failed to install mouse hook.")
            return
        print("Mouse hook running.")

        # ── WinEvent hook: hide the overlay when its native menu closes ──
        # Counts menu nesting so a SUBMENU opening/closing (a normal END
        # while the parent stays open) doesn't hide the button prematurely;
        # only the last menu closing does. Chromium / in-page menus emit no
        # such events, so those fall through to the 3 s timer untouched.
        WINEVENTPROC = ctypes.WINFUNCTYPE(
            None, ctypes.c_void_p, wintypes.DWORD, wintypes.HWND,
            wintypes.LONG, wintypes.LONG, wintypes.DWORD, wintypes.DWORD)
        user32.SetWinEventHook.restype  = ctypes.c_void_p
        user32.SetWinEventHook.argtypes = [
            wintypes.DWORD, wintypes.DWORD, wintypes.HMODULE, WINEVENTPROC,
            wintypes.DWORD, wintypes.DWORD, wintypes.DWORD]
        user32.UnhookWinEvent.restype  = wintypes.BOOL
        user32.UnhookWinEvent.argtypes = [ctypes.c_void_p]

        def winevent_proc(hHook, event, hwnd, idObj, idChild, thread, ts):
            try:
                self._on_menu_event(event)
            except Exception:
                pass

        self._winevent_proc_ref = WINEVENTPROC(winevent_proc)
        self._winevent_hook = user32.SetWinEventHook(
            EVENT_SYSTEM_MENUPOPUPSTART, EVENT_SYSTEM_MENUPOPUPEND,
            None, self._winevent_proc_ref, 0, 0,
            WINEVENT_OUTOFCONTEXT | WINEVENT_SKIPOWNPROCESS)

        msg = wintypes.MSG()
        while self.running:
            result = user32.GetMessageW(ctypes.byref(msg), None, 0, 0)
            if result <= 0:
                break
            ctypes.windll.user32.TranslateMessage(ctypes.byref(msg))
            ctypes.windll.user32.DispatchMessageW(ctypes.byref(msg))
        if self._winevent_hook:
            user32.UnhookWinEvent(self._winevent_hook)
            self._winevent_hook = None
        if self.hook_id:
            user32.UnhookWindowsHookEx(self.hook_id)
            self.hook_id = None
            print("Mouse hook removed.")

    def _on_menu_event(self, event):
        """Native menu opened/closed (WinEvent thread). Tracks nesting so
        only the LAST menu closing hides the overlay — a submenu closing
        while its parent stays open must not. Emits on the signal so the
        actual hide runs on the Qt main thread."""
        if event == EVENT_SYSTEM_MENUPOPUPSTART:
            self._menu_open_count += 1
        elif event == EVENT_SYSTEM_MENUPOPUPEND:
            self._menu_open_count -= 1
            if self._menu_open_count <= 0:
                self._menu_open_count = 0
                self._signals.hide_overlay.emit()

    def _uninstall_mouse_hook(self):
        if self.hook_thread_id:
            ctypes.windll.user32.PostThreadMessageW(self.hook_thread_id, WM_QUIT, 0, 0)

    # ── Hotkey ────────────────────────────────────────────────────────────────

    def _setup_hotkey(self):
        """Bind every configurable shortcut. Combos come from settings
        (Settings → Shortcuts) with SHORTCUT_DEFS defaults."""
        self._hotkeys = {}   # settings_key → bound combo
        for key, _label, default in SHORTCUT_DEFS:
            try:
                combo = self.history.settings.get(key, default) or default
            except Exception:
                combo = default
            try:
                keyboard.add_hotkey(combo, self._make_hotkey_cb(key),
                                    suppress=True)
                self._hotkeys[key] = combo
                print(f"Hotkey registered: {combo}  ({key})")
            except Exception as e:
                print(f"Hotkey error for '{combo}' ({key}): {e}")

    def _make_hotkey_cb(self, key: str):
        # Hotkey callbacks run on the keyboard library's thread — emit a
        # signal so the action executes on the Qt main thread.
        return lambda: self._signals.run_action.emit(key)

    def set_hotkey(self, key: str, combo: str) -> bool:
        """Re-bind one shortcut live (Settings → Shortcuts). Returns True
        on success; on failure the old binding is restored."""
        old = self._hotkeys.get(key) if hasattr(self, "_hotkeys") else None
        if not hasattr(self, "_hotkeys"):
            self._hotkeys = {}
        if old:
            try:
                keyboard.remove_hotkey(old)
            except Exception:
                pass
        try:
            keyboard.add_hotkey(combo, self._make_hotkey_cb(key), suppress=True)
            self._hotkeys[key] = combo
            print(f"Hotkey registered: {combo}  ({key})")
            return True
        except Exception as e:
            print(f"Hotkey error for '{combo}' ({key}): {e}")
            if old:   # restore the previous working binding
                try:
                    keyboard.add_hotkey(old, self._make_hotkey_cb(key),
                                        suppress=True)
                    self._hotkeys[key] = old
                except Exception:
                    self._hotkeys.pop(key, None)
            return False

    # ── Hotkey actions (all run on the Qt main thread) ───────────────────────

    def _dispatch_action(self, key: str):
        try:
            if key == "hotkey_open":
                self._action_open()
            elif key == "hotkey_pause":
                self._action_toggle_pause()
            elif key == "hotkey_snippet":
                self._action_new_snippet()
            elif key == "hotkey_clear":
                self._action_clear_history()
            elif key == "hotkey_profile":
                self._action_next_profile()
        except Exception as e:
            print(f"[ClipDrop] Hotkey action '{key}' failed: {e}")

    def _action_open(self):
        try:
            self.popup._paste_target = win32gui.GetForegroundWindow()
        except Exception:
            self.popup._paste_target = None
        x, y = pyautogui.position()
        self.popup.show(x, y)

    def _action_toggle_pause(self):
        watcher = getattr(self.popup, "watcher", None)
        if watcher is None:
            return
        watcher.paused = not watcher.paused
        self.popup._show_toast(
            "⏸ Clipboard capture paused" if watcher.paused
            else "▶ Clipboard capture resumed")

    def _action_new_snippet(self):
        from snippet_window import SnippetWindow
        win = getattr(self, "_snippet_win", None)
        if win is not None and win.isVisible():
            win.raise_()
            win.activateWindow()
            return
        self._snippet_win = SnippetWindow(self.history, popup=self.popup)
        self._snippet_win.show()
        self._snippet_win.activateWindow()

    def _action_clear_history(self):
        # Destructive — a stray hotkey press must not wipe everything.
        reply = QMessageBox.question(
            None, "Clear History",
            "Clear ALL clipboard history?\n\nThis cannot be undone.",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No)
        if reply != QMessageBox.StandardButton.Yes:
            return
        self.history.clear_all()
        self.popup._refresh()          # no-op when the popup is closed
        self.popup._show_toast("History cleared")

    def _action_next_profile(self):
        profiles = getattr(self.popup, "profiles", None)
        if profiles is None:
            return
        profs = profiles.get_all_profiles()
        if not profs:
            return
        active = profiles.get_active_profile()["id"]
        idx    = next((i for i, p in enumerate(profs) if p["id"] == active), 0)
        nxt    = profs[(idx + 1) % len(profs)]
        profiles.set_active(nxt["id"])
        self.popup._refresh()          # no-op when the popup is closed
        self.popup._show_toast(f"Profile: {nxt['name']}")

    # ── Registry ──────────────────────────────────────────────────────────────

    def _register_in_registry(self):
        pythonw = sys.executable.replace("python.exe", "pythonw.exe")
        if not os.path.exists(pythonw):
            pythonw = sys.executable
        command = (f'"{pythonw}" -c "import tempfile, pyautogui; '
                   r"open(tempfile.gettempdir()+chr(92)+'clipdrop.signal','w').write(str(pyautogui.position()))" + '"')
        for reg_path in REG_PATHS:
            try:
                key = winreg.CreateKeyEx(winreg.HKEY_CURRENT_USER,
                    r"Software\Classes\\" + reg_path, 0,
                    winreg.KEY_SET_VALUE | winreg.KEY_CREATE_SUB_KEY)
                winreg.SetValueEx(key, "", 0, winreg.REG_SZ, "Paste from ClipDrop")
                winreg.SetValueEx(key, "Icon", 0, winreg.REG_SZ, sys.executable)
                winreg.CloseKey(key)
                cmd_key = winreg.CreateKeyEx(winreg.HKEY_CURRENT_USER,
                    r"Software\Classes\\" + reg_path + r"\command", 0, winreg.KEY_SET_VALUE)
                winreg.SetValueEx(cmd_key, "", 0, winreg.REG_SZ, command)
                winreg.CloseKey(cmd_key)
            except Exception as e:
                print(f"Registry error: {e}")

    def _remove_from_registry(self):
        for reg_path in REG_PATHS:
            try:
                winreg.DeleteKey(winreg.HKEY_CURRENT_USER,
                    r"Software\Classes\\" + reg_path + r"\command")
                winreg.DeleteKey(winreg.HKEY_CURRENT_USER,
                    r"Software\Classes\\" + reg_path)
            except Exception:
                pass
