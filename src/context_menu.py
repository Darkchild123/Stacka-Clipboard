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

from PyQt6.QtWidgets import QWidget, QLabel, QHBoxLayout, QApplication
from PyQt6.QtCore    import Qt, QTimer, pyqtSignal, QObject

# ---- Windows API constants ----
WH_MOUSE_LL   = 14
WM_RBUTTONUP  = 0x0205
WM_LBUTTONDOWN = 0x0201
WM_QUIT       = 0x0012

HOTKEY = "ctrl+shift+v"

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
        self._timer.stop()
        self.adjustSize()
        w = self.width(); h = self.height()
        screen = QApplication.primaryScreen().geometry()
        sw, sh = screen.width(), screen.height()

        if menu_rect:
            pos_x, pos_y = self._best_position(menu_rect, w, h, sw, sh)
        else:
            PAD = 10; EDGE = 5
            in_dead = (sw*0.40 <= x <= sw*0.60 and sh*0.40 <= y <= sh*0.60)
            pos_x = max(EDGE, x - w - PAD) if (in_dead or x < sw//2) else min(x+PAD, sw-w-EDGE)
            pos_y = max(EDGE, y - h - PAD) if y < sh//2 else min(y+PAD, sh-h-EDGE)

        self.move(pos_x, pos_y)
        self.show()
        self._apply_no_activate()
        self.raise_()
        self._timer.start(3000)

    def _best_position(self, menu_rect, btn_w, btn_h, sw, sh):
        ml, mt, mr, mb = menu_rect
        PAD = 10; EDGE = 5
        def clamp(x, y):
            return (max(EDGE, min(x, sw-btn_w-EDGE)),
                    max(EDGE, min(y, sh-btn_h-EDGE)))
        def overlaps(x, y):
            return x < mr and x+btn_w > ml and y < mb and y+btn_h > mt
        space = [mt-EDGE-PAD, sh-mb-EDGE-PAD, ml-EDGE-PAD, sw-mr-EDGE-PAD]
        raw   = [(space[0]-btn_h, ml, mt-btn_h-PAD),
                 (space[1]-btn_h, ml, mb+PAD),
                 (space[2]-btn_w, ml-btn_w-PAD, mt),
                 (space[3]-btn_w, mr+PAD, mt)]
        raw.sort(key=lambda c: c[0], reverse=True)
        for _, rx, ry in raw:
            cx, cy = clamp(rx, ry)
            if not overlaps(cx, cy):
                return cx, cy
        _, rx, ry = raw[0]
        return clamp(rx, ry)

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
        try:
            keyboard.remove_hotkey(HOTKEY)
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
                menu_rect = self._find_context_menu_rect()
                if menu_rect:
                    break
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

    def _find_context_menu_rect(self):
        found = []
        def cb(hwnd, _):
            try:
                if win32gui.IsWindowVisible(hwnd):
                    if win32gui.GetClassName(hwnd) == "#32768":
                        rect = win32gui.GetWindowRect(hwnd)
                        if rect[2]-rect[0] > 10 and rect[3]-rect[1] > 10:
                            found.append(rect)
            except Exception:
                pass
        try:
            win32gui.EnumWindows(cb, None)
        except Exception:
            pass
        return found[0] if found else None

    def _on_overlay_clicked(self):
        self.popup._paste_target = self._right_click_target
        x, y = pyautogui.position()
        self.popup.show(x, y)

    # ── Hide popup on outside click ───────────────────────────────────────────

    def _on_hide_popup_if_outside(self, click_x, click_y):
        win = getattr(self.popup, "_popup", None)
        if not win or not win.isVisible():
            return
        try:
            gx, gy = win.x(), win.y()
            gw, gh = win.width(), win.height()
            inside = (gx <= click_x <= gx+gw and gy <= click_y <= gy+gh)
            if not inside:
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

        def hook_proc(nCode, wParam, lParam):
            try:
                if nCode >= 0:
                    ms = ctypes.cast(lParam, ctypes.POINTER(MSLLHOOKSTRUCT)).contents
                    x, y = ms.pt.x, ms.pt.y
                    if wParam == WM_RBUTTONUP:
                        self._show_overlay(x, y)
                    elif wParam == WM_LBUTTONDOWN:
                        self._signals.hide_popup_if_outside.emit(x, y)
            except Exception as e:
                print(f"Hook proc error: {e}")
            return user32.CallNextHookEx(self.hook_id, nCode, wParam, lParam)

        self._hook_proc_ref = HOOKPROC(hook_proc)
        self.hook_id = user32.SetWindowsHookExW(WH_MOUSE_LL, self._hook_proc_ref, None, 0)
        if not self.hook_id:
            print("Failed to install mouse hook.")
            return
        print("Mouse hook running.")
        msg = wintypes.MSG()
        while self.running:
            result = user32.GetMessageW(ctypes.byref(msg), None, 0, 0)
            if result <= 0:
                break
            ctypes.windll.user32.TranslateMessage(ctypes.byref(msg))
            ctypes.windll.user32.DispatchMessageW(ctypes.byref(msg))
        if self.hook_id:
            user32.UnhookWindowsHookEx(self.hook_id)
            self.hook_id = None
            print("Mouse hook removed.")

    def _uninstall_mouse_hook(self):
        if self.hook_thread_id:
            ctypes.windll.user32.PostThreadMessageW(self.hook_thread_id, WM_QUIT, 0, 0)

    # ── Hotkey ────────────────────────────────────────────────────────────────

    def _setup_hotkey(self):
        try:
            keyboard.add_hotkey(HOTKEY, self._on_hotkey_triggered, suppress=True)
            print(f"Hotkey registered: {HOTKEY}")
        except Exception as e:
            print(f"Hotkey error: {e}")

    def _on_hotkey_triggered(self):
        try:
            self.popup._paste_target = win32gui.GetForegroundWindow()
        except Exception:
            self.popup._paste_target = None
        x, y = pyautogui.position()
        self.popup.show(x, y)

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
