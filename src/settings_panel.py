# ============================================================
# ClipDrop - settings_panel.py  (PyQt6 rewrite)
# ============================================================
# Settings window — lets the user control ClipDrop behaviour.
# Opened from the system tray icon menu.
# ============================================================

import webbrowser

from PyQt6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout,
    QLabel, QLineEdit, QPushButton, QSlider,
    QListWidget, QListWidgetItem, QFrame,
    QInputDialog, QMessageBox, QApplication, QScrollArea,
    QKeySequenceEdit,
)
from PyQt6.QtCore    import Qt, QTimer, QEvent, QVariantAnimation
from PyQt6.QtGui     import QFont, QIntValidator, QCursor, QKeySequence

import math

APP_NAME    = "ClipDrop"
APP_VERSION = "1.0.0"
APP_AUTHOR  = "Cosmas Nwachukwu"
APP_EMAIL   = "finecosmas@gmail.com"
GITHUB_URL  = "https://github.com/Darkchild123/Project-ClipDrop"

DARK = {
    "bg":           "#1e1e2e",
    "bg_section":   "#2a2a3e",
    "bg_input":     "#13131f",
    "accent":       "#4f46e5",
    "accent_hover": "#6366f1",
    "text":         "#e2e8f0",
    "text_dim":     "#94a3b8",
    "danger":       "#ef4444",
    "danger_hover": "#dc2626",
    "success":      "#22c55e",
    "border":       "#3f3f5f",
}

LIGHT = {
    "bg":           "#f8fafc",
    "bg_section":   "#f1f5f9",
    "bg_input":     "#e2e8f0",
    "accent":       "#4f46e5",
    "accent_hover": "#6366f1",
    "text":         "#1e293b",
    "text_dim":     "#64748b",
    "danger":       "#ef4444",
    "danger_hover": "#dc2626",
    "success":      "#16a34a",
    "border":       "#cbd5e1",
}


def _lerp(c1: str, c2: str, t: float) -> str:
    r1,g1,b1 = int(c1[1:3],16), int(c1[3:5],16), int(c1[5:7],16)
    r2,g2,b2 = int(c2[1:3],16), int(c2[3:5],16), int(c2[5:7],16)
    return "#{:02x}{:02x}{:02x}".format(
        int(r1+(r2-r1)*t), int(g1+(g2-g1)*t), int(b1+(b2-b1)*t))

def _shade(col: str, t: float) -> str:
    """Lighten (t>0) or darken (t<0) a hex colour."""
    return _lerp(col, "#ffffff" if t >= 0 else "#000000", abs(t))

def _grad_v(top: str, bottom: str) -> str:
    return (f"qlineargradient(x1:0,y1:0,x2:0,y2:1,"
            f"stop:0 {top},stop:1 {bottom})")

def _btn_style(bg: str, hover: str, fg: str = "white") -> str:
    """Raised 3D button: gradient face, darker seam border, brighter on
    hover, and a pressed state that darkens and shifts the label 1px
    down — the classic press-in effect."""
    face   = _grad_v(_shade(bg, 0.16), _shade(bg, -0.12))
    hface  = _grad_v(_shade(hover, 0.18), _shade(hover, -0.06))
    press  = _shade(bg, -0.28)
    seam   = _shade(bg, -0.30)
    return (f"QPushButton {{background:{face};color:{fg};"
            f"font-family:'Segoe UI';font-size:9pt;"
            f"padding:5px 12px;border-radius:4px;"
            f"border:1px solid {seam};}}"
            f"QPushButton:hover {{background:{hface};}}"
            f"QPushButton:pressed {{background:{press};"
            f"padding-top:6px;padding-bottom:4px;}}")


def _scrollbar_qss(C: dict) -> str:
    """Modern scrollbar matching the popup's: transparent track, rounded
    gradient handle in ACCENT colour (visible while inactive), brighter
    on hover, lightest while dragging."""
    handle_top = _shade(C["accent"], 0.12)
    handle_bot = _shade(C["accent"], -0.22)
    hover      = _shade(C["accent"], 0.32)
    return (
        f"QScrollBar:vertical {{background:transparent;width:10px;"
        f"margin:2px 2px 2px 0;border:none;}}"
        f"QScrollBar::handle:vertical {{"
        f"background:qlineargradient(x1:0,y1:0,x2:1,y2:0,"
        f"stop:0 {handle_top},stop:1 {handle_bot});"
        f"border-radius:4px;min-height:28px;}}"
        f"QScrollBar::handle:vertical:hover {{background:{hover};}}"
        f"QScrollBar::handle:vertical:pressed {{background:{C['accent_hover']};}}"
        f"QScrollBar::add-line:vertical,QScrollBar::sub-line:vertical {{height:0;}}"
        f"QScrollBar::add-page:vertical,QScrollBar::sub-page:vertical "
        f"{{background:none;}}")


# ── Shortcuts ────────────────────────────────────────────────────────────────
# The canonical shortcut table lives in context_menu.py (which owns the
# actual bindings). The Shortcuts window builds its rows from it.
try:
    from context_menu import SHORTCUT_DEFS
except Exception:   # import edge in isolated tests
    SHORTCUT_DEFS = [
        ("hotkey_open", "Open ClipDrop popup window", "ctrl+shift+v"),
    ]

# Combos already taken by Windows or near-universal app functions.
# Assigning one of these gets a WARNING (not a block — the binding wins
# system-wide via the low-level hook, but the user should know what
# they're stealing).
KNOWN_COMBOS = {
    "ctrl+c": "Copy",              "ctrl+v": "Paste",
    "ctrl+x": "Cut",               "ctrl+z": "Undo",
    "ctrl+y": "Redo",              "ctrl+a": "Select All",
    "ctrl+s": "Save",              "ctrl+p": "Print",
    "ctrl+f": "Find",              "ctrl+w": "Close Tab",
    "ctrl+t": "New Tab",           "ctrl+n": "New Window",
    "alt+f4": "Close Window",      "alt+tab": "Switch Windows",
    "ctrl+shift+esc": "Task Manager",
    "ctrl+alt+del": "Security Screen",
    "f1": "Help",                  "f5": "Refresh",
    "win+l": "Lock PC",            "win+d": "Show Desktop",
}


def _titlebar_dark(widget, dark: bool):
    """Match a window's native title bar to the theme via DWM
    (Win10 1903+ / Win11; silent no-op elsewhere)."""
    try:
        import ctypes
        val  = ctypes.c_int(1 if dark else 0)
        hwnd = int(widget.winId())
        for attr in (20, 19):   # DWMWA_USE_IMMERSIVE_DARK_MODE (19 pre-20H1)
            if ctypes.windll.dwmapi.DwmSetWindowAttribute(
                    hwnd, attr, ctypes.byref(val), 4) == 0:
                break
    except Exception:
        pass


class ShortcutsWindow(QWidget):
    """Shortcut management window (Settings → Shortcuts).

    Lists every entry of SHORTCUT_DEFS with a key-capture field, per-row
    reset, and a Save that re-binds live through the running ContextMenu
    (via the app-level 'clipdrop_context' property).
    """

    def __init__(self, history_manager, parent=None):
        super().__init__(parent,
                         Qt.WindowType.Window |
                         Qt.WindowType.WindowStaysOnTopHint |
                         Qt.WindowType.WindowCloseButtonHint)
        self.history = history_manager
        self._theme  = history_manager.settings.get("theme", "dark")
        self.C       = DARK if self._theme == "dark" else LIGHT
        self._edits       = {}     # settings_key → QKeySequenceEdit
        self._listen_btns = {}     # settings_key → listen QPushButton
        self._edit_owner  = {}     # QKeySequenceEdit → settings_key
        self._prev_seq    = {}     # settings_key → sequence before listening
        self._labels      = {k: lbl for k, lbl, _ in SHORTCUT_DEFS}
        self._listening_key = None

        # Pulse animation for the active listen button (loops until a
        # combo is captured or focus leaves the field)
        self._pulse = QVariantAnimation(self)
        self._pulse.setDuration(900)
        self._pulse.setStartValue(0.0)
        self._pulse.setEndValue(1.0)
        self._pulse.setLoopCount(-1)
        self._pulse.valueChanged.connect(self._on_pulse)

        self.setWindowTitle("ClipDrop Shortcuts")
        self.setFixedWidth(470)
        self._build()

        self.adjustSize()
        screen = QApplication.screenAt(QCursor.pos()) or QApplication.primaryScreen()
        fg = self.frameGeometry()
        fg.moveCenter(screen.availableGeometry().center())
        self.move(fg.topLeft())
        _titlebar_dark(self, self._theme == "dark")

    def _build(self):
        C = self.C
        self.setStyleSheet(f"QWidget {{background:{C['bg']};}} "
                           f"QLabel {{color:{C['text']};background:transparent;}}")

        main = QVBoxLayout(self)
        main.setContentsMargins(0, 0, 0, 0)
        main.setSpacing(0)

        hdr = QLabel("⌨️  Shortcuts", self)
        hdr.setFont(QFont("Segoe UI", 12, QFont.Weight.Bold))
        hdr.setAlignment(Qt.AlignmentFlag.AlignCenter)
        hdr.setFixedHeight(44)
        hdr.setStyleSheet(
            f"background:{_grad_v(C['accent_hover'], _shade(C['accent'], -0.18))};"
            f"color:white;border-bottom:1px solid rgba(0,0,0,90);")
        main.addWidget(hdr)

        body = QVBoxLayout()
        body.setContentsMargins(16, 12, 16, 12)
        body.setSpacing(8)

        sub = QLabel("Click ⏺ (or the field) and press the key combination "
                     "you want — the button pulses while listening. "
                     "Save applies immediately.", self)
        sub.setWordWrap(True)
        sub.setStyleSheet(f"color:{C['text_dim']};font-size:8pt;background:transparent;")
        body.addWidget(sub)

        for key, label, default in SHORTCUT_DEFS:
            row = QWidget(self); row.setStyleSheet(f"background:{C['bg']};")
            rl = QHBoxLayout(row); rl.setContentsMargins(0, 4, 0, 4); rl.setSpacing(8)

            lbl = QLabel(label, row)
            lbl.setStyleSheet(f"color:{C['text']};background:transparent;")
            rl.addWidget(lbl, 1)

            edit = QKeySequenceEdit(row)
            try:                       # Qt ≥ 6.4 — capture ONE combo only
                edit.setMaximumSequenceLength(1)
            except AttributeError:
                pass
            current = self.history.settings.get(key, default) or default
            edit.setKeySequence(QKeySequence(current))
            edit.setFixedWidth(130)
            # NOTE: QKeySequenceEdit renders through an INTERNAL QLineEdit —
            # styling only the outer widget leaves the text in the default
            # (dark-on-dark) palette. The child selector is what makes the
            # combo text actually visible.
            edit.setStyleSheet(f"""
                QKeySequenceEdit {{background:{C['bg_input']};
                    border:1px solid {C['border']};border-radius:4px;
                    padding:2px 4px;}}
                QKeySequenceEdit QLineEdit {{background:transparent;
                    color:{C['text']};border:none;
                    font-family:'Segoe UI';font-size:9pt;}}
            """)
            self._edits[key] = edit
            self._edit_owner[edit] = key
            edit.installEventFilter(self)     # focus in/out drives listening
            edit.editingFinished.connect(
                lambda k=key: self._set_listening(k, False))
            # Live conflict warning the moment a combo is captured
            edit.keySequenceChanged.connect(
                lambda _seq, k=key: self._check_conflicts(k))
            rl.addWidget(edit)

            listen = QPushButton("⏺", row)
            listen.setFixedWidth(30)
            listen.setToolTip("Listen for a new key combination")
            listen.setCursor(Qt.CursorShape.PointingHandCursor)
            listen.setStyleSheet(_btn_style(C["bg_section"], C["accent"], C["text_dim"]))
            listen.clicked.connect(lambda _=False, k=key: self._begin_listen(k))
            self._listen_btns[key] = listen
            rl.addWidget(listen)

            reset = QPushButton("↺", row)
            reset.setFixedWidth(30)
            reset.setToolTip(f"Reset to {default}")
            reset.setStyleSheet(_btn_style(C["bg_section"], C["accent"], C["text_dim"]))
            reset.clicked.connect(
                lambda _=False, e=edit, d=default: e.setKeySequence(QKeySequence(d)))
            rl.addWidget(reset)

            clear = QPushButton("✕", row)
            clear.setFixedWidth(30)
            clear.setToolTip("Unassign — leave this action with no shortcut")
            clear.setStyleSheet(_btn_style(C["bg_section"], C["danger"], C["text_dim"]))
            clear.clicked.connect(
                lambda _=False, e=edit, k=key: (e.clearFocus(), e.clear(),
                                                self._check_conflicts(k)))
            rl.addWidget(clear)
            body.addWidget(row)

        # Footer: feedback + Save/Close
        foot = QWidget(self); foot.setStyleSheet(f"background:{C['bg']};")
        fl = QHBoxLayout(foot); fl.setContentsMargins(0, 8, 0, 0); fl.setSpacing(8)
        self._feedback_lbl = QLabel("", foot)
        self._feedback_lbl.setStyleSheet(f"color:{C['success']};background:transparent;")
        fl.addWidget(self._feedback_lbl, 1)
        save = QPushButton("Save", foot)
        save.setFixedWidth(90)
        save.setStyleSheet(_btn_style(C["accent"], C["accent_hover"]))
        save.clicked.connect(self._save)
        fl.addWidget(save)
        close = QPushButton("Close", foot)
        close.setFixedWidth(90)
        close.setStyleSheet(_btn_style(C["bg_section"], C["accent"], C["text_dim"]))
        close.clicked.connect(self.close)
        fl.addWidget(close)
        body.addWidget(foot)

        main.addLayout(body)

    # ── Listening state (pulsing ⏺ button) ───────────────────────────────────

    def eventFilter(self, obj, ev):
        key = self._edit_owner.get(obj)
        if key is not None:
            if ev.type() == QEvent.Type.FocusIn:
                self._set_listening(key, True)
            elif ev.type() == QEvent.Type.FocusOut:
                self._set_listening(key, False)
        return False

    def _begin_listen(self, key: str):
        edit = self._edits[key]
        # Remember the current combo so an aborted capture restores it
        self._prev_seq[key] = edit.keySequence()
        edit.clear()
        edit.setFocus(Qt.FocusReason.MouseFocusReason)
        self._set_listening(key, True)

    def _set_listening(self, key: str, on: bool):
        if on:
            if self._listening_key == key:
                return
            self._stop_listen_visual()
            self._listening_key = key
            self._pulse.start()
        else:
            if self._listening_key != key:
                return
            self._stop_listen_visual()
            # Aborted with an empty field → restore the previous combo
            edit = self._edits[key]
            if edit.keySequence().isEmpty() and key in self._prev_seq:
                edit.setKeySequence(self._prev_seq[key])

    def _stop_listen_visual(self):
        self._pulse.stop()
        k, self._listening_key = self._listening_key, None
        if k is not None and k in self._listen_btns:
            self._listen_btns[k].setStyleSheet(
                _btn_style(self.C["bg_section"], self.C["accent"],
                           self.C["text_dim"]))

    def _on_pulse(self, v):
        k = self._listening_key
        if k is None:
            return
        # Smooth 0→1→0 wave per loop
        s = (1 - math.cos(2 * math.pi * float(v))) / 2
        col = _lerp(self.C["bg_section"], self.C["accent"], s)
        self._listen_btns[k].setStyleSheet(
            f"QPushButton {{background:{col};color:white;border-radius:4px;"
            f"padding:5px 0;border:1px solid {self.C['accent']};"
            f"font-size:9pt;}}")

    # ── Conflict warnings (live, on capture) ─────────────────────────────────

    def _combo_of(self, key: str) -> str:
        return self._edits[key].keySequence().toString().replace(" ", "").lower()

    def _mark_edit(self, key: str, conflict: bool):
        C = self.C
        border = C["danger"] if conflict else C["border"]
        self._edits[key].setStyleSheet(f"""
            QKeySequenceEdit {{background:{C['bg_input']};
                border:1px solid {border};border-radius:4px;
                padding:2px 4px;}}
            QKeySequenceEdit QLineEdit {{background:transparent;
                color:{C['text']};border:none;
                font-family:'Segoe UI';font-size:9pt;}}
        """)

    def _check_conflicts(self, key: str):
        """Warn immediately when a freshly captured combo is already
        assigned to another ClipDrop action (field turns red) or is a
        well-known Windows / app shortcut (warning only)."""
        combo  = self._combo_of(key)
        pretty = self._edits[key].keySequence().toString()
        if not combo:
            self._mark_edit(key, conflict=False)
            return
        # Taken by another ClipDrop action?
        for other, _lbl, _d in SHORTCUT_DEFS:
            if other != key and self._combo_of(other) == combo:
                self._mark_edit(key, conflict=True)
                self._feedback(
                    f"⚠ {pretty} is already assigned to "
                    f"“{self._labels.get(other, other)}”", ok=False)
                return
        self._mark_edit(key, conflict=False)
        # Taken by Windows / a near-universal app function?
        if combo in KNOWN_COMBOS:
            self._feedback(
                f"⚠ {pretty} is already in use by Windows "
                f"({KNOWN_COMBOS[combo]}) — it will be overridden", ok=False)
            return
        self._feedback_lbl.setText("")   # conflict resolved — clear warning

    # ── Save ─────────────────────────────────────────────────────────────────

    def _feedback(self, msg: str, ok: bool = True):
        col = self.C["success"] if ok else self.C["danger"]
        self._feedback_lbl.setStyleSheet(f"color:{col};background:transparent;")
        self._feedback_lbl.setText(msg)
        QTimer.singleShot(2500, lambda: self._feedback_lbl.setText(""))

    def _save(self):
        # Pass 1: collect + validate. An EMPTY combo means "unassigned" —
        # allowed (the action simply has no shortcut). Duplicates among the
        # non-empty ones are still rejected.
        combos = {}
        seen   = {}
        for key, label, default in SHORTCUT_DEFS:
            seq   = self._edits[key].keySequence().toString()   # "Ctrl+Shift+V"
            combo = seq.replace(" ", "").lower()                # keyboard-lib format
            if combo:
                if combo in seen:
                    self._feedback(f"{seq} is assigned twice", ok=False)
                    return
                seen[combo] = key
            combos[key] = (combo, seq)

        # Pass 2: re-bind live. Empty combo → unbind the action. On a bind
        # failure the old binding is restored by set_hotkey; nothing further
        # is saved.
        ctx = QApplication.instance().property("clipdrop_context")
        for key, (combo, seq) in combos.items():
            if ctx is not None:
                if not ctx.set_hotkey(key, combo):     # combo="" → unbind
                    self._feedback(f"Could not bind {seq}", ok=False)
                    return
            self.history.save_setting(key, combo)
        self._feedback("✓ Saved — active now")


class SettingsPanel(QWidget):
    """Settings panel.

    Uses QWidget (not QDialog) so there is no built-in accept/reject/
    Enter-to-close behaviour. A global event filter provides click-outside-
    to-close so the panel feels like a lightweight floating panel.
    """

    def __init__(self, history_manager, profile_manager=None, parent=None):
        super().__init__(parent,
                         Qt.WindowType.Window |
                         Qt.WindowType.WindowStaysOnTopHint |
                         Qt.WindowType.WindowMinimizeButtonHint |
                         Qt.WindowType.WindowCloseButtonHint)
        self.history  = history_manager
        self.profiles = profile_manager
        self._theme   = history_manager.settings.get("theme", "dark")
        self.C        = DARK if self._theme == "dark" else LIGHT
        self._shortcuts_win = None   # keep reference — prevents GC close

        self.setWindowTitle("ClipDrop Settings")
        self.setFixedWidth(420)
        self.setWindowOpacity(history_manager.settings.get("transparency", 1.0))

        self._build()

        # Centre cleanly on the screen the cursor is on.
        # adjustSize() first so frameGeometry() reflects the real size of
        # the built layout, then moveCenter() — the standard Qt centring
        # pattern. availableGeometry() excludes the taskbar.
        self.adjustSize()
        screen = QApplication.screenAt(QCursor.pos()) or QApplication.primaryScreen()
        fg = self.frameGeometry()
        fg.moveCenter(screen.availableGeometry().center())
        self.move(fg.topLeft())

        # Native title bar follows the app theme (dark/light)
        self._apply_titlebar_theme()

        # Install global event filter for click-outside-to-close
        QApplication.instance().installEventFilter(self)

    def _apply_titlebar_theme(self):
        """Match the native Windows title bar to the app theme."""
        _titlebar_dark(self, self._theme == "dark")

    # ── Click-outside-to-close ────────────────────────────────────────────────

    def eventFilter(self, obj, event):
        # A minimized window is still isVisible() in Qt terms — clicking
        # another ClipDrop window must not close a minimized settings panel.
        if (event.type() == QEvent.Type.MouseButtonPress
                and self.isVisible() and not self.isMinimized()):
            try:
                gpos = event.globalPosition().toPoint()
                # A click inside the Shortcuts window must not close us
                sw = self._shortcuts_win
                if (sw is not None and sw.isVisible()
                        and sw.frameGeometry().contains(gpos)):
                    return False
                # Check this window and all its child widgets
                if not self.geometry().contains(gpos):
                    # Allow clicks on QMessageBox / QInputDialog (they are
                    # separate windows — their geometry won't match ours, but
                    # they are children of this panel logically)
                    focused = QApplication.activeWindow()
                    if focused is not None and focused is not self:
                        # A child dialog (QMessageBox etc.) is active — don't close
                        return False
                    self.close()
            except Exception:
                pass
        return False   # never consume the event

    def closeEvent(self, event):
        # Remove the global event filter when the panel closes
        try:
            QApplication.instance().removeEventFilter(self)
        except Exception:
            pass
        super().closeEvent(event)

    def _build(self):
        C = self.C
        self.setStyleSheet(f"QWidget {{background:{C['bg']};}} "
                           f"QLabel {{color:{C['text']};background:transparent;}}")

        main = QVBoxLayout(self)
        main.setContentsMargins(0, 0, 0, 0)
        main.setSpacing(0)

        # Header — gradient surface with a dark seam (raised 3D look)
        hdr = QLabel("📋  ClipDrop Settings", self)
        hdr.setFont(QFont("Segoe UI", 13, QFont.Weight.Bold))
        hdr.setAlignment(Qt.AlignmentFlag.AlignCenter)
        hdr.setFixedHeight(48)
        hdr.setStyleSheet(
            f"background:{_grad_v(C['accent_hover'], _shade(C['accent'], -0.18))};"
            f"color:white;border-bottom:1px solid rgba(0,0,0,90);")
        main.addWidget(hdr)

        # Scrollable content — the window stays compact; sections that
        # don't fit are reached by scrolling.
        scroll_w = QWidget()
        scroll_w.setStyleSheet(f"background:{C['bg']};")
        scroll_lay = QVBoxLayout(scroll_w)
        scroll_lay.setContentsMargins(16, 8, 16, 8)
        scroll_lay.setSpacing(0)

        scroll_lay.addWidget(self._section_appearance())
        scroll_lay.addWidget(self._divider())
        scroll_lay.addWidget(self._section_sizing())
        scroll_lay.addWidget(self._divider())
        scroll_lay.addWidget(self._section_icons())
        scroll_lay.addWidget(self._divider())
        scroll_lay.addWidget(self._section_trigger())
        scroll_lay.addWidget(self._divider())
        scroll_lay.addWidget(self._section_behaviour())
        scroll_lay.addWidget(self._divider())
        scroll_lay.addWidget(self._section_shortcuts())
        scroll_lay.addWidget(self._divider())
        scroll_lay.addWidget(self._section_history())
        if self.profiles:
            scroll_lay.addWidget(self._divider())
            scroll_lay.addWidget(self._section_profiles())
        scroll_lay.addWidget(self._divider())
        scroll_lay.addWidget(self._section_info())
        scroll_lay.addStretch()

        scroll = QScrollArea(self)
        scroll.setWidget(scroll_w)
        scroll.setWidgetResizable(True)
        scroll.setFrameShape(QFrame.Shape.NoFrame)
        scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        scroll.setStyleSheet(f"QScrollArea {{background:{C['bg']};border:none;}}"
                             + _scrollbar_qss(C))
        main.addWidget(scroll, 1)

        # Footer close button
        footer = QWidget(self)
        footer.setStyleSheet(f"background:{C['bg_section']};")
        fl = QHBoxLayout(footer)
        fl.setContentsMargins(16, 8, 16, 8)
        close_btn = QPushButton("Close", footer)
        close_btn.setFixedWidth(100)
        close_btn.setStyleSheet(_btn_style(C["accent"], C["accent_hover"]))
        close_btn.clicked.connect(self.close)
        fl.addStretch()
        fl.addWidget(close_btn)
        fl.addStretch()
        main.addWidget(footer)

        # Compact window: header + ~2 sections visible, rest scrolls.
        self.setFixedHeight(520)

    def _divider(self) -> QFrame:
        line = QFrame(self)
        line.setFrameShape(QFrame.Shape.HLine)
        line.setStyleSheet(f"color:{self.C['border']};margin:4px 8px;")
        return line

    def _section_appearance(self) -> QWidget:
        C = self.C
        w = QWidget(self); w.setStyleSheet(f"background:{C['bg']};")
        lay = QVBoxLayout(w); lay.setContentsMargins(0,8,0,8); lay.setSpacing(6)

        lay.addWidget(self._heading("🎨  Appearance"))

        # Theme toggle
        theme_row = QWidget(w); theme_row.setStyleSheet(f"background:{C['bg']};")
        tr = QHBoxLayout(theme_row); tr.setContentsMargins(0,0,0,0); tr.setSpacing(8)
        lbl = QLabel("Theme:", w); lbl.setFixedWidth(80)
        lbl.setStyleSheet(f"color:{C['text']};background:transparent;")
        tr.addWidget(lbl)

        self._dark_btn  = QPushButton("🌙  Dark",  w)
        self._light_btn = QPushButton("☀️  Light", w)
        self._dark_btn.setFixedWidth(90)
        self._light_btn.setFixedWidth(90)
        self._refresh_theme_buttons()
        self._dark_btn.clicked.connect(lambda: self._set_theme("dark"))
        self._light_btn.clicked.connect(lambda: self._set_theme("light"))
        tr.addWidget(self._dark_btn)
        tr.addWidget(self._light_btn)
        tr.addStretch()
        lay.addWidget(theme_row)

        # Transparency slider
        lbl2 = QLabel("Popup transparency:", w)
        lbl2.setStyleSheet(f"color:{C['text']};background:transparent;")
        lay.addWidget(lbl2)

        slider_row = QWidget(w); slider_row.setStyleSheet(f"background:{C['bg']};")
        sr = QHBoxLayout(slider_row); sr.setContentsMargins(0,0,0,0); sr.setSpacing(8)
        current_opacity = max(50, int(self.history.settings.get("transparency", 1.0) * 100))
        self._slider = QSlider(Qt.Orientation.Horizontal, w)
        self._slider.setRange(50, 100)
        self._slider.setValue(current_opacity)
        self._slider.setFixedWidth(200)
        self._slider.setStyleSheet(f"""
            QSlider::groove:horizontal {{background:{C['bg_section']};height:6px;border-radius:3px;}}
            QSlider::handle:horizontal {{background:{C['accent']};width:14px;height:14px;
                border-radius:7px;margin:-4px 0;}}
        """)
        self._opacity_lbl = QLabel(f"{current_opacity}%", w)
        self._opacity_lbl.setStyleSheet(f"color:{C['text_dim']};background:transparent;")
        self._opacity_lbl.setFixedWidth(40)
        self._slider.valueChanged.connect(self._on_opacity_change)
        sr.addWidget(self._slider)
        sr.addWidget(self._opacity_lbl)
        sr.addStretch()
        lay.addWidget(slider_row)

        # Row hover colour — a strip of clickable swatches
        hv_row = QWidget(w); hv_row.setStyleSheet(f"background:{C['bg']};")
        hr = QHBoxLayout(hv_row); hr.setContentsMargins(0,2,0,0); hr.setSpacing(6)
        hlbl = QLabel("Row hover:", w); hlbl.setFixedWidth(80)
        hlbl.setStyleSheet(f"color:{C['text']};background:transparent;")
        hr.addWidget(hlbl)
        self._hover_colour = self.history.settings.get("hover_colour", "default")
        self._hover_swatches = {}
        for key, name, swatch in self.HOVER_CHOICES:
            b = QPushButton("", hv_row)
            b.setFixedSize(22, 22)
            b.setCursor(Qt.CursorShape.PointingHandCursor)
            b.setToolTip(name)
            b.clicked.connect(lambda _=False, k=key: self._set_hover_colour(k))
            self._hover_swatches[key] = (b, swatch)
            hr.addWidget(b)
        hr.addStretch()
        self._refresh_hover_swatches()
        lay.addWidget(hv_row)
        return w

    HOVER_CHOICES = [
        ("default", "Indigo",  "#6366f1"),
        ("gold",    "Gold",    "#d4a017"),
        ("emerald", "Emerald", "#0e9f6e"),
        ("rose",    "Rose",    "#e11d6b"),
        ("sky",     "Sky",     "#0ea5e9"),
        ("violet",  "Violet",  "#7c3aed"),
        ("slate",   "Slate",   "#64748b"),
    ]

    def _refresh_hover_swatches(self):
        for key, (btn, swatch) in self._hover_swatches.items():
            sel = key == self._hover_colour
            ring = "#ffffff" if sel else self.C["border"]
            width = 3 if sel else 1
            btn.setStyleSheet(
                f"QPushButton{{background:{swatch};border:{width}px solid {ring};"
                f"border-radius:5px;}}")

    def _set_hover_colour(self, key: str):
        if key == self._hover_colour:
            return
        self._hover_colour = key
        self.history.save_setting("hover_colour", key)
        self._refresh_hover_swatches()
        self._apply_to_app()

    # (mode key, button label, one-line caption)
    TRIGGER_MODES = [
        ("double_right", "🖱  Double right-click",
         "Right-click twice quickly to open ClipDrop at the cursor. "
         "One hand, never covers the app's own menu."),
        ("middle", "🖱  Middle-click",
         "Press the scroll wheel to open ClipDrop. One hand, no menu flash. "
         "Overrides middle-click's usual open-in-new-tab / autoscroll."),
        ("side", "⏪  Mouse side button",
         "Use a thumb Back/Forward button to open ClipDrop. "
         "Needs a mouse with side buttons."),
        ("ctrl_right", "⌨  Ctrl + right-click",
         "Hold Ctrl and right-click to open ClipDrop. Plain right-click "
         "stays normal. No menu flash."),
        ("button", "🔘  Overlay button",
         "A “Paste from ClipDrop” button appears beside the cursor on "
         "every right-click."),
        ("hotkey", "⌨  Hotkey only",
         "No mouse trigger — open ClipDrop only with your keyboard "
         "shortcut (see Shortcuts)."),
    ]

    # (settings key, label) — each slider is 60–120% in 10% steps,
    # 100% = the app's default size. Deliberately caption-free: at this
    # window width a per-row caption wraps to 2-3 lines and triples the
    # section's height.
    # Percent sliders (60–120% in 10% steps). The main window is resized by
    # dragging its edges, so it has no slider here — only row size.
    SIZE_SLIDERS = [
        ("scale_row", "Row size"),
    ]

    def _section_sizing(self) -> QWidget:
        C = self.C
        w = QWidget(self); w.setStyleSheet(f"background:{C['bg']};")
        lay = QVBoxLayout(w); lay.setContentsMargins(0,4,0,4); lay.setSpacing(2)

        head = QWidget(w); head.setStyleSheet(f"background:{C['bg']};")
        hl = QHBoxLayout(head); hl.setContentsMargins(0,0,0,0); hl.setSpacing(8)
        hl.addWidget(self._heading("📐  Sizing"))
        hint = QLabel("10% steps · 100% = default", head)
        hint.setStyleSheet(f"color:{C['text_dim']};font-size:8pt;background:transparent;")
        hl.addWidget(hint); hl.addStretch()
        lay.addWidget(head)

        # One debounce timer for all sliders: rebuild the popup once the
        # user settles, not on every step of a drag.
        self._size_timer = QTimer(self)
        self._size_timer.setSingleShot(True)
        self._size_timer.timeout.connect(self._apply_to_app)

        self._size_lbls = {}
        for key, label in self.SIZE_SLIDERS:
            row = QWidget(w); row.setStyleSheet(f"background:{C['bg']};")
            row.setFixedHeight(24)
            rl = QHBoxLayout(row); rl.setContentsMargins(0,0,0,0); rl.setSpacing(8)

            name = QLabel(label, row); name.setFixedWidth(88)
            name.setStyleSheet(f"color:{C['text']};background:transparent;")
            rl.addWidget(name)

            # Slider works in 10% units (6..12) so every position is a
            # valid step — no snapping logic, no invalid sizes.
            pct = int(self.history.settings.get(key, 100))
            pct = max(60, min(120, int(round(pct / 10.0) * 10)))
            sld = QSlider(Qt.Orientation.Horizontal, row)
            sld.setRange(6, 12)
            sld.setValue(pct // 10)
            sld.setSingleStep(1); sld.setPageStep(1)
            sld.setFixedWidth(210)
            sld.setStyleSheet(f"""
                QSlider::groove:horizontal {{background:{C['bg_section']};height:5px;border-radius:3px;}}
                QSlider::handle:horizontal {{background:{C['accent']};width:13px;height:13px;
                    border-radius:7px;margin:-4px 0;}}
            """)
            val = QLabel(f"{pct}%", row); val.setFixedWidth(40)
            val.setStyleSheet(f"color:{C['text_dim']};background:transparent;")
            sld.valueChanged.connect(
                lambda v, k=key, l=val: self._on_size_change(k, v, l))
            self._size_lbls[key] = val
            rl.addWidget(sld); rl.addWidget(val); rl.addStretch()
            lay.addWidget(row)

        # ── Side list rows: a COUNT (1–20), not a percent ──
        row = QWidget(w); row.setStyleSheet(f"background:{C['bg']};")
        row.setFixedHeight(24)
        rl = QHBoxLayout(row); rl.setContentsMargins(0,0,0,0); rl.setSpacing(8)
        name = QLabel("Side list rows", row); name.setFixedWidth(88)
        name.setStyleSheet(f"color:{C['text']};background:transparent;")
        rl.addWidget(name)
        rows = max(1, min(20, int(self.history.settings.get("side_list_rows", 10))))
        rsld = QSlider(Qt.Orientation.Horizontal, row)
        rsld.setRange(1, 20); rsld.setValue(rows)
        rsld.setSingleStep(1); rsld.setPageStep(1); rsld.setFixedWidth(210)
        rsld.setStyleSheet(f"""
            QSlider::groove:horizontal {{background:{C['bg_section']};height:5px;border-radius:3px;}}
            QSlider::handle:horizontal {{background:{C['accent']};width:13px;height:13px;
                border-radius:7px;margin:-4px 0;}}
        """)
        rval = QLabel(str(rows), row); rval.setFixedWidth(40)
        rval.setStyleSheet(f"color:{C['text_dim']};background:transparent;")
        rsld.valueChanged.connect(self._on_side_rows_change)
        self._side_rows_lbl = rval
        rl.addWidget(rsld); rl.addWidget(rval); rl.addStretch()
        lay.addWidget(row)

        # ── Main window font size (80–140% in 10% steps) ──
        frow = QWidget(w); frow.setStyleSheet(f"background:{C['bg']};")
        frow.setFixedHeight(24)
        fl = QHBoxLayout(frow); fl.setContentsMargins(0,0,0,0); fl.setSpacing(8)
        fname = QLabel("Font size", frow); fname.setFixedWidth(88)
        fname.setStyleSheet(f"color:{C['text']};background:transparent;")
        fl.addWidget(fname)
        fpct = max(80, min(140, int(round(int(self.history.settings.get("font_scale",100))/10.0)*10)))
        fsld = QSlider(Qt.Orientation.Horizontal, frow)
        fsld.setRange(8, 14); fsld.setValue(fpct // 10)
        fsld.setSingleStep(1); fsld.setPageStep(1); fsld.setFixedWidth(210)
        fsld.setStyleSheet(f"""
            QSlider::groove:horizontal {{background:{C['bg_section']};height:5px;border-radius:3px;}}
            QSlider::handle:horizontal {{background:{C['accent']};width:13px;height:13px;
                border-radius:7px;margin:-4px 0;}}
        """)
        fval = QLabel(f"{fpct}%", frow); fval.setFixedWidth(40)
        fval.setStyleSheet(f"color:{C['text_dim']};background:transparent;")
        fsld.valueChanged.connect(self._on_font_change)
        self._font_lbl = fval
        fl.addWidget(fsld); fl.addWidget(fval); fl.addStretch()
        lay.addWidget(frow)
        return w

    def _on_font_change(self, steps: int):
        pct = steps * 10
        self._font_lbl.setText(f"{pct}%")
        self.history.save_setting("font_scale", pct)
        self._size_timer.start(180)

    def _on_size_change(self, key: str, steps: int, label: QLabel):
        pct = steps * 10
        label.setText(f"{pct}%")
        self.history.save_setting(key, pct)
        self._size_timer.start(180)   # debounce → one popup rebuild

    def _on_side_rows_change(self, n: int):
        self._side_rows_lbl.setText(str(n))
        self.history.save_setting("side_list_rows", int(n))
        self._size_timer.start(180)

    ICON_PACKS = [
        ("default", "🎨  Default ClipDrop",
         "Colourful modern icons — Office letter tiles, the Python logo, "
         "gears, and more."),
        ("labeled", "🏷  Labeled documents",
         "Document-style icons with the file extension shown as a badge "
         "(PDF, DOCX, PNG…), one per extension."),
    ]

    def _section_icons(self) -> QWidget:
        C = self.C
        w = QWidget(self); w.setStyleSheet(f"background:{C['bg']};")
        lay = QVBoxLayout(w); lay.setContentsMargins(0,8,0,8); lay.setSpacing(6)

        lay.addWidget(self._heading("🖼️  Icon pack"))
        self._icon_pack = self.history.settings.get("icon_pack", "default")
        self._icon_pack_btns = {}
        for pack, label, caption in self.ICON_PACKS:
            row = QWidget(w); row.setStyleSheet(f"background:{C['bg']};")
            rl = QHBoxLayout(row); rl.setContentsMargins(0,0,0,0); rl.setSpacing(8)
            btn = QPushButton(label, row)
            btn.setFixedWidth(165)
            btn.clicked.connect(lambda _=False, p=pack: self._set_icon_pack(p))
            rl.addWidget(btn)
            cap = QLabel(caption, row); cap.setWordWrap(True)
            cap.setStyleSheet(f"color:{C['text_dim']};font-size:8pt;background:transparent;")
            rl.addWidget(cap, 1)
            self._icon_pack_btns[pack] = btn
            lay.addWidget(row)
        self._refresh_icon_pack_buttons()
        return w

    def _refresh_icon_pack_buttons(self):
        C = self.C
        active   = _btn_style(C["accent"], C["accent_hover"])
        inactive = _btn_style(C["bg_section"], C["accent"], C["text_dim"])
        for pack, btn in self._icon_pack_btns.items():
            btn.setStyleSheet(active if pack == self._icon_pack else inactive)

    def _set_icon_pack(self, pack: str):
        if pack == self._icon_pack:
            return
        self._icon_pack = pack
        self.history.save_setting("icon_pack", pack)
        self._refresh_icon_pack_buttons()
        self._apply_to_app()   # open popup rebuilds with the new pack

    def _section_trigger(self) -> QWidget:
        C = self.C
        w = QWidget(self); w.setStyleSheet(f"background:{C['bg']};")
        lay = QVBoxLayout(w); lay.setContentsMargins(0,8,0,8); lay.setSpacing(6)

        lay.addWidget(self._heading("🖱️  Popup trigger"))
        hint = QLabel("Pick up to two — e.g. overlay button + double "
                      "right-click. “Hotkey only” can’t be combined.", w)
        hint.setWordWrap(True)
        hint.setStyleSheet(f"color:{C['text_dim']};font-size:8pt;"
                           f"background:transparent;")
        lay.addWidget(hint)
        self._triggers = self._read_triggers()
        self._trigger_btns = {}

        for mode, label, caption in self.TRIGGER_MODES:
            row = QWidget(w); row.setStyleSheet(f"background:{C['bg']};")
            rl = QHBoxLayout(row); rl.setContentsMargins(0,0,0,0); rl.setSpacing(8)
            btn = QPushButton(label, row)
            btn.setFixedWidth(165)
            btn.clicked.connect(lambda _=False, m=mode: self._toggle_trigger(m))
            rl.addWidget(btn)
            cap = QLabel(caption, row)
            cap.setWordWrap(True)
            cap.setStyleSheet(f"color:{C['text_dim']};font-size:8pt;background:transparent;")
            rl.addWidget(cap, 1)
            self._trigger_btns[mode] = btn
            lay.addWidget(row)

        self._refresh_trigger_buttons()
        return w

    def _refresh_trigger_buttons(self):
        C = self.C
        active   = _btn_style(C["accent"], C["accent_hover"])
        inactive = _btn_style(C["bg_section"], C["accent"], C["text_dim"])
        for mode, btn in self._trigger_btns.items():
            btn.setStyleSheet(active if mode in self._triggers else inactive)

    def _read_triggers(self):
        """Current trigger selection (1–2), migrating the legacy single
        'trigger_mode' and enforcing hotkey exclusivity."""
        s = self.history.settings
        trs = s.get("triggers")
        if not isinstance(trs, list) or not trs:
            trs = [s.get("trigger_mode", "double_right")]
        valid = {m for m, _, _ in self.TRIGGER_MODES}
        trs = [t for t in trs if t in valid]
        if not trs:
            trs = ["double_right"]
        if "hotkey" in trs:          # hotkey can't be paired
            trs = ["hotkey"]
        return trs[:2]

    def _toggle_trigger(self, mode: str):
        """Toggle a trigger in/out of the selection (up to two). 'Hotkey only'
        is exclusive — picking it clears the rest, and picking any mouse
        trigger clears it. The last active trigger can't be switched off (there
        must always be one), and picking a third drops the oldest."""
        trs = list(self._triggers)
        if mode == "hotkey":
            trs = ["hotkey"]                         # exclusive
        else:
            trs = [t for t in trs if t != "hotkey"]  # leaving hotkey-only
            if mode in trs:
                trs.remove(mode)
                if not trs:                          # never leave it empty
                    trs = [mode]
            else:
                trs.append(mode)
                if len(trs) > 2:
                    trs.pop(0)                        # keep the last two
        self._triggers = trs
        self.history.save_setting("triggers", trs)
        # Mirror the first choice into the legacy key for backward compat.
        self.history.save_setting("trigger_mode", trs[0])
        self._refresh_trigger_buttons()

    def _section_behaviour(self) -> QWidget:
        C = self.C
        w = QWidget(self); w.setStyleSheet(f"background:{C['bg']};")
        lay = QVBoxLayout(w); lay.setContentsMargins(0,8,0,8); lay.setSpacing(6)

        lay.addWidget(self._heading("🪟  Close behaviour"))
        self._close_mode = self.history.settings.get("close_mode", "click")

        def option_row(label, mode, caption):
            row = QWidget(w); row.setStyleSheet(f"background:{C['bg']};")
            rl = QHBoxLayout(row); rl.setContentsMargins(0,0,0,0); rl.setSpacing(8)
            btn = QPushButton(label, row)
            btn.setFixedWidth(140)
            btn.clicked.connect(lambda _=False, m=mode: self._set_close_mode(m))
            rl.addWidget(btn)
            cap = QLabel(caption, row)
            cap.setWordWrap(True)
            cap.setStyleSheet(f"color:{C['text_dim']};font-size:8pt;background:transparent;")
            rl.addWidget(cap, 1)
            return row, btn

        r1, self._click_close_btn = option_row(
            "🖱  Click to close", "click",
            "Click anywhere outside the app window and it closes.")
        r2, self._hover_close_btn = option_row(
            "👆  Hover to close", "hover",
            "Hover outside the app window automatically closes it.")
        lay.addWidget(r1)
        lay.addWidget(r2)
        self._refresh_close_mode_buttons()
        return w

    def _refresh_close_mode_buttons(self):
        C = self.C
        active   = _btn_style(C["accent"], C["accent_hover"])
        inactive = _btn_style(C["bg_section"], C["accent"], C["text_dim"])
        self._click_close_btn.setStyleSheet(
            active if self._close_mode == "click" else inactive)
        self._hover_close_btn.setStyleSheet(
            active if self._close_mode == "hover" else inactive)

    def _set_close_mode(self, mode: str):
        if mode == self._close_mode:
            return
        self._close_mode = mode
        self.history.save_setting("close_mode", mode)
        self._refresh_close_mode_buttons()
        self._apply_to_app()   # open popup re-evaluates its close mode

    def _section_shortcuts(self) -> QWidget:
        C = self.C
        w = QWidget(self); w.setStyleSheet(f"background:{C['bg']};")
        lay = QVBoxLayout(w); lay.setContentsMargins(0,8,0,8); lay.setSpacing(6)

        lay.addWidget(self._heading("⌨️  Shortcuts"))
        row = QWidget(w); row.setStyleSheet(f"background:{C['bg']};")
        rl = QHBoxLayout(row); rl.setContentsMargins(0,0,0,0); rl.setSpacing(8)
        btn = QPushButton("Manage Shortcuts…", row)
        btn.setFixedWidth(150)
        btn.setStyleSheet(_btn_style(C["accent"], C["accent_hover"]))
        btn.clicked.connect(self._open_shortcuts)
        rl.addWidget(btn)
        cur = self.history.settings.get("hotkey_open", "ctrl+shift+v")
        cap = QLabel(f"Launch ClipDrop:  {cur.upper()}", row)
        cap.setStyleSheet(f"color:{C['text_dim']};font-size:8pt;background:transparent;")
        rl.addWidget(cap)
        rl.addStretch()
        lay.addWidget(row)
        return w

    def _open_shortcuts(self):
        if self._shortcuts_win and self._shortcuts_win.isVisible():
            self._shortcuts_win.raise_()
            self._shortcuts_win.activateWindow()
            return
        self._shortcuts_win = ShortcutsWindow(self.history)
        self._shortcuts_win.show()

    def _section_history(self) -> QWidget:
        C = self.C
        w = QWidget(self); w.setStyleSheet(f"background:{C['bg']};")
        lay = QVBoxLayout(w); lay.setContentsMargins(0,8,0,8); lay.setSpacing(6)

        lay.addWidget(self._heading("🗂   History"))

        row = QWidget(w); row.setStyleSheet(f"background:{C['bg']};")
        rl = QHBoxLayout(row); rl.setContentsMargins(0,0,0,0); rl.setSpacing(8)
        lbl = QLabel("History size limit:", row)
        lbl.setStyleSheet(f"color:{C['text']};background:transparent;")
        rl.addWidget(lbl)

        self._limit_edit = QLineEdit(str(self.history.get_limit()), row)
        self._limit_edit.setFixedWidth(60)
        self._limit_edit.setValidator(QIntValidator(1, 1000))
        self._limit_edit.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self._limit_edit.setStyleSheet(f"""
            QLineEdit {{background:{C['bg_input']};color:{C['text']};
            border:none;border-radius:4px;padding:4px;font-family:'Segoe UI';font-size:10pt;}}
        """)
        rl.addWidget(self._limit_edit)
        lbl2 = QLabel("items", row); lbl2.setStyleSheet(f"color:{C['text_dim']};background:transparent;")
        rl.addWidget(lbl2)
        rl.addStretch()
        lay.addWidget(row)

        btn_row = QWidget(w); btn_row.setStyleSheet(f"background:{C['bg']};")
        bl = QHBoxLayout(btn_row); bl.setContentsMargins(0,0,0,0); bl.setSpacing(8)
        save_btn = QPushButton("Save Limit", btn_row)
        save_btn.setFixedWidth(100)
        save_btn.setStyleSheet(_btn_style(C["accent"], C["accent_hover"]))
        save_btn.clicked.connect(self._save_limit)
        bl.addWidget(save_btn)
        self._save_feedback = QLabel("", btn_row)
        self._save_feedback.setStyleSheet(f"color:{C['success']};background:transparent;")
        bl.addWidget(self._save_feedback)
        bl.addStretch()
        lay.addWidget(btn_row)

        clear_btn = QPushButton("🧹  Clear All History", w)
        clear_btn.setStyleSheet(_btn_style(C["danger"], C["danger_hover"]))
        clear_btn.clicked.connect(self._confirm_clear)
        lay.addWidget(clear_btn)
        return w

    def _section_profiles(self) -> QWidget:
        C = self.C
        w = QWidget(self); w.setStyleSheet(f"background:{C['bg']};")
        lay = QVBoxLayout(w); lay.setContentsMargins(0,8,0,8); lay.setSpacing(6)

        lay.addWidget(self._heading("👤  Profiles"))
        sub = QLabel("Organise your clipboard into named workflow collections.", w)
        sub.setStyleSheet(f"color:{C['text_dim']};font-size:8pt;background:transparent;")
        lay.addWidget(sub)

        self._profile_list = QListWidget(w)
        self._profile_list.setFixedHeight(80)
        self._profile_list.setStyleSheet(f"""
            QListWidget {{background:{C['bg_input']};color:{C['text']};border:1px solid {C['border']};
                border-radius:4px;font-family:'Segoe UI';font-size:10pt;}}
            QListWidget::item:selected {{background:{C['accent']};color:white;}}
        """)
        lay.addWidget(self._profile_list)
        self._refresh_profile_list()

        def btn_row(buttons):
            rw = QWidget(w); rw.setStyleSheet(f"background:{C['bg']};")
            rl = QHBoxLayout(rw); rl.setContentsMargins(0,0,0,0); rl.setSpacing(6)
            for label, cmd, danger in buttons:
                b = QPushButton(label, rw)
                style = _btn_style(C["danger"] if danger else C["bg_section"],
                                   C["danger_hover"] if danger else C["accent"],
                                   "white")
                b.setStyleSheet(style)
                b.clicked.connect(cmd)
                rl.addWidget(b)
            rl.addStretch()
            return rw

        lay.addWidget(btn_row([
            ("✔ Switch To", self._switch_profile,  False),
            ("＋ New",      self._new_profile,    False),
            ("✎ Rename",    self._rename_profile, False),
            ("✕ Delete",    self._delete_profile, False),
        ]))
        lay.addWidget(btn_row([
            ("↑ Move Up",   self._move_profile_up,        False),
            ("↓ Move Down", self._move_profile_down,      False),
            ("🧹 Clear",    self._clear_selected_profile, True),
        ]))

        # Double-click also switches profile
        self._profile_list.itemDoubleClicked.connect(
            lambda _: self._switch_profile()
        )
        return w

    def _section_info(self) -> QWidget:
        C = self.C
        w = QWidget(self); w.setStyleSheet(f"background:{C['bg']};")
        lay = QVBoxLayout(w); lay.setContentsMargins(0,8,0,8); lay.setSpacing(4)

        lay.addWidget(self._heading("ℹ️   About ClipDrop"))
        for label, value in [("Version", APP_VERSION), ("Author", APP_AUTHOR),
                               ("Email", APP_EMAIL), ("Platform", "Windows")]:
            row = QWidget(w); row.setStyleSheet(f"background:{C['bg']};")
            rl = QHBoxLayout(row); rl.setContentsMargins(0,0,0,0)
            lbl = QLabel(f"{label}:", row)
            lbl.setFixedWidth(80)
            lbl.setStyleSheet(f"color:{C['text_dim']};background:transparent;")
            val = QLabel(value, row)
            val.setStyleSheet(f"color:{C['text']};background:transparent;")
            rl.addWidget(lbl); rl.addWidget(val); rl.addStretch()
            lay.addWidget(row)

        # GitHub link
        row = QWidget(w); row.setStyleSheet(f"background:{C['bg']};")
        rl = QHBoxLayout(row); rl.setContentsMargins(0,0,0,0)
        lbl = QLabel("GitHub:", row)
        lbl.setFixedWidth(80)
        lbl.setStyleSheet(f"color:{C['text_dim']};background:transparent;")
        link = QLabel(f'<a href="{GITHUB_URL}" style="color:{C["accent_hover"]};">{GITHUB_URL}</a>', row)
        link.setOpenExternalLinks(True)
        link.setTextFormat(Qt.TextFormat.RichText)
        link.setStyleSheet("background:transparent;")
        rl.addWidget(lbl); rl.addWidget(link); rl.addStretch()
        lay.addWidget(row)
        return w

    def _heading(self, text: str) -> QLabel:
        lbl = QLabel(text, self)
        lbl.setFont(QFont("Segoe UI", 10, QFont.Weight.Bold))
        lbl.setStyleSheet(f"color:{self.C['text']};background:transparent;")
        return lbl

    # ── Theme ─────────────────────────────────────────────────────────────────

    def _refresh_theme_buttons(self):
        C = self.C
        active   = _btn_style(C["accent"], C["accent_hover"])
        inactive = _btn_style(C["bg_section"], C["accent"], C["text_dim"])
        if self._theme == "dark":
            self._dark_btn.setStyleSheet(active)
            self._light_btn.setStyleSheet(inactive)
        else:
            self._dark_btn.setStyleSheet(inactive)
            self._light_btn.setStyleSheet(active)

    def _set_theme(self, theme: str):
        if theme == self._theme:
            return
        self._theme = theme
        self.C = DARK if theme == "dark" else LIGHT
        self.history.save_setting("theme", theme)
        self._rebuild_ui()             # this window restyles instantly…
        self._apply_titlebar_theme()   # …including the native title bar…
        self._apply_to_app()           # …and so does the open popup

    def _rebuild_ui(self):
        """Tear down and rebuild the whole panel with the current palette.

        Every section bakes colours into its stylesheets at build time, so
        a palette change requires a rebuild. It happens in one event-loop
        turn at fixed size — visually it's an instant restyle, no flicker.
        """
        old = self.layout()
        if old is not None:
            while old.count():
                it = old.takeAt(0)
                w = it.widget()
                if w is not None:
                    w.deleteLater()
            # A widget can only ever have one layout — hand the old one to
            # a throwaway widget so _build() can install a fresh QVBoxLayout.
            QWidget().setLayout(old)
        self._build()
        self.adjustSize()

    def _apply_to_app(self):
        """Push appearance changes to the live app popup (if open).
        full=True: theme changes restyle the window CHROME (card, header
        gradient, scrollbars), which needs the popup's full rebuild path —
        plain data refreshes stay in-place and flicker-free."""
        try:
            popup = QApplication.instance().property("clipdrop_popup")
            if popup is not None and getattr(popup, "_popup", None):
                popup._refresh(full=True)
        except Exception:
            pass

    # ── Opacity ───────────────────────────────────────────────────────────────

    def _on_opacity_change(self, value: int):
        opacity = value / 100.0
        self.setWindowOpacity(opacity)
        self._opacity_lbl.setText(f"{value}%")
        self.history.save_setting("transparency", opacity)
        # Live-apply to the open popup while the slider drags — a direct
        # opacity set, no rebuild needed, so it tracks smoothly.
        try:
            popup = QApplication.instance().property("clipdrop_popup")
            if popup is not None and getattr(popup, "_popup", None):
                popup._popup.setWindowOpacity(opacity)
        except Exception:
            pass

    # ── History ───────────────────────────────────────────────────────────────

    def _save_limit(self):
        try:
            value = int(self._limit_edit.text())
            if not (1 <= value <= 1000):
                QMessageBox.warning(self, "Invalid Value",
                    "History limit must be between 1 and 1000.")
                return
            self.history.set_limit(value)
            # Same universal limit applies to every profile — each trims its
            # own copies independently.
            self.profiles.enforce_all_limits()
            self._save_feedback.setText("✓  Saved!")
            QTimer.singleShot(2000, lambda: self._save_feedback.setText(""))
        except ValueError:
            QMessageBox.warning(self, "Invalid Value",
                "Please enter a whole number.")

    def _confirm_clear(self):
        reply = QMessageBox.question(self, "Clear History",
            "Clear all clipboard history?\n\nThis cannot be undone.",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No)
        if reply == QMessageBox.StandardButton.Yes:
            self.history.clear_all()
            QMessageBox.information(self, "Done", "Clipboard history has been cleared.")

    # ── Profile actions ───────────────────────────────────────────────────────

    def _refresh_profile_list(self):
        if not hasattr(self, "_profile_list"):
            return
        self._profile_list.clear()
        for p in self.profiles.get_all_profiles():
            count  = self.profiles.get_profile_item_count(p["id"])
            active = "● " if p["id"] == self.profiles.active_id else "  "
            lock   = " 🔒" if p.get("built_in") else ""
            self._profile_list.addItem(f"{active}{p['name']}{lock}  ({count} items)")

    def _selected_profile(self):
        items = self._profile_list.selectedItems()
        if not items:
            return None
        idx = self._profile_list.row(items[0])
        profs = self.profiles.get_all_profiles()
        return profs[idx] if idx < len(profs) else None

    def _switch_profile(self):
        p = self._selected_profile()
        if not p:
            QMessageBox.information(self, "Switch Profile",
                "Select a profile first."); return
        self.profiles.set_active(p["id"])
        self._refresh_profile_list()

    def _new_profile(self):
        name, ok = QInputDialog.getText(self, "New Profile", "Profile name:")
        if ok and name.strip():
            self.profiles.create_profile(name.strip())
            self._refresh_profile_list()

    def _rename_profile(self):
        p = self._selected_profile()
        if not p:
            QMessageBox.information(self, "Rename", "Select a profile first."); return
        if p.get("built_in"):
            QMessageBox.information(self, "Rename", "General cannot be renamed."); return
        name, ok = QInputDialog.getText(self, "Rename Profile",
            f"New name for '{p['name']}':", text=p["name"])
        if ok and name.strip():
            self.profiles.rename_profile(p["id"], name.strip())
            self._refresh_profile_list()

    def _delete_profile(self):
        p = self._selected_profile()
        if not p:
            QMessageBox.information(self, "Delete", "Select a profile first."); return
        if p.get("built_in"):
            QMessageBox.information(self, "Delete", "General cannot be deleted."); return
        reply = QMessageBox.question(self, "Delete Profile",
            f"Delete profile '{p['name']}'?\n\nItems stay in General.",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No)
        if reply == QMessageBox.StandardButton.Yes:
            self.profiles.delete_profile(p["id"])
            self._refresh_profile_list()

    def _clear_selected_profile(self):
        p = self._selected_profile()
        if not p:
            QMessageBox.information(self, "Clear", "Select a profile first."); return
        if p["id"] == "general":
            reply = QMessageBox.question(self, "Clear General",
                "Clear all items from General?\n\nItems in named profiles stay there. "
                "Others are permanently deleted.\n\nThis cannot be undone.",
                QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No)
            if reply == QMessageBox.StandardButton.Yes:
                # Export model: named profiles hold their own copies, so
                # clearing General simply empties the live history.
                self.history.clear_all()
                self._refresh_profile_list()
                QMessageBox.information(self, "Done",
                    "General cleared.\nNamed profiles keep their own copies.")
        else:
            reply = QMessageBox.question(self, "Clear Profile",
                f"Clear all items from '{p['name']}'?\n\nItems stay in General.",
                QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No)
            if reply == QMessageBox.StandardButton.Yes:
                self.profiles.clear_profile(p["id"])
                self._refresh_profile_list()
                QMessageBox.information(self, "Done", f"'{p['name']}' cleared.")

    def _move_profile_up(self):
        p = self._selected_profile()
        if p:
            self.profiles.move_up(p["id"])
            self._refresh_profile_list()

    def _move_profile_down(self):
        p = self._selected_profile()
        if p:
            self.profiles.move_down(p["id"])
            self._refresh_profile_list()
