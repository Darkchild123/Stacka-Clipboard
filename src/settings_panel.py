# ============================================================
# Stacka - settings_panel.py  (PyQt6 rewrite)
# ============================================================
# Settings window — lets the user control Stacka behaviour.
# Opened from the system tray icon menu.
# ============================================================

from PyQt6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout,
    QLabel, QLineEdit, QPushButton, QSlider,
    QListWidget, QListWidgetItem, QFrame,
    QInputDialog, QMessageBox, QApplication, QScrollArea,
    QKeySequenceEdit, QComboBox,
)
from PyQt6.QtCore    import Qt, QTimer, QEvent, QVariantAnimation
from PyQt6.QtGui     import QFont, QIntValidator, QCursor, QKeySequence

import math

import i18n
import auto_wipe
import app_paths

APP_NAME    = "Stacka"
APP_VERSION = "1.0.0"
APP_AUTHOR  = "Cosmas Nwachukwu"
APP_EMAIL   = "finecosmas@gmail.com"
GITHUB_URL  = "https://github.com/Darkchild123/Stacka-Clipboard"
GITHUB_PROFILE_URL = "https://github.com/Darkchild123"

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
        ("hotkey_open", "Open Stacka popup window", "ctrl+shift+v"),
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
    (via the app-level 'stacka_context' property).
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

        self.setWindowTitle("Stacka Shortcuts")
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
        assigned to another Stacka action (field turns red) or is a
        well-known Windows / app shortcut (warning only)."""
        combo  = self._combo_of(key)
        pretty = self._edits[key].keySequence().toString()
        if not combo:
            self._mark_edit(key, conflict=False)
            return
        # Taken by another Stacka action?
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
        ctx = QApplication.instance().property("stacka_context")
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

        self.setWindowTitle("Stacka Settings")
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
        # another Stacka window must not close a minimized settings panel.
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

        # Header — gradient surface with a dark seam (raised 3D look), now
        # carrying the app title on the left and the language selector right.
        hdr = QWidget(self)
        hdr.setFixedHeight(48)
        hdr.setStyleSheet(
            f"background:{_grad_v(C['accent_hover'], _shade(C['accent'], -0.18))};"
            f"border-bottom:1px solid rgba(0,0,0,90);")
        hl = QHBoxLayout(hdr)
        hl.setContentsMargins(16, 0, 10, 0)
        title = QLabel("📋  " + i18n.tr("Settings"), hdr)
        title.setFont(QFont("Segoe UI", 13, QFont.Weight.Bold))
        title.setStyleSheet("color:white;background:transparent;")
        hl.addWidget(title)
        hl.addStretch()
        hl.addWidget(self._build_lang_combo(hdr))
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
        close_btn = QPushButton(i18n.tr("Close"), footer)
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

    def _build_lang_combo(self, parent) -> QComboBox:
        """Language selector for the header — each language shown in its own
        name (endonym); the active one is what's displayed when it's closed."""
        C = self.C
        combo = QComboBox(parent)
        for code, name in i18n.LANGUAGES:
            combo.addItem(name, code)
        idx = combo.findData(self.history.settings.get("language", "en"))
        if idx >= 0:
            combo.setCurrentIndex(idx)          # set BEFORE connect — no stray fire
        combo.setFixedWidth(122)
        combo.setCursor(Qt.CursorShape.PointingHandCursor)
        combo.setStyleSheet(
            "QComboBox{background:rgba(0,0,0,55);color:white;border:1px solid "
            "rgba(255,255,255,70);border-radius:5px;padding:2px 8px;}"
            "QComboBox::drop-down{subcontrol-origin:padding;subcontrol-position:center right;"
            "border:none;width:20px;}"
            "QComboBox::down-arrow{width:0;height:0;margin-right:7px;"
            "border-left:5px solid transparent;border-right:5px solid transparent;"
            "border-top:6px solid white;}"
            f"QComboBox QAbstractItemView{{background:{C['bg_section']};"
            f"color:{C['text']};selection-background-color:{C['accent']};"
            "selection-color:white;outline:none;}")
        combo.currentIndexChanged.connect(self._on_language_changed)
        return combo

    def _on_language_changed(self, idx: int):
        combo = self.sender()
        code = combo.itemData(idx) if combo is not None else None
        if not code or code == self.history.settings.get("language", "en"):
            return
        self.history.save_setting("language", code)
        i18n.set_language(code)

        # Everything that is built ONCE and then kept has to be relabelled by
        # hand, or it stays stuck in the previous language until a restart.
        app = QApplication.instance()

        # The tray menu is created at startup and never rebuilt.
        tray = app.property("stacka_tray") if app else None
        if tray is not None:
            try:
                tray.retranslate()
            except Exception as e:
                print(f"[Stacka] Tray retranslate failed: {e}")

        # The Shortcuts window, if the user has it open.
        if self._shortcuts_win is not None:
            try:
                if self._shortcuts_win.isVisible():
                    self._shortcuts_win.close()
            except RuntimeError:
                self._shortcuts_win = None

        # Re-render the whole panel in the new language (same path as a theme
        # change — deferred widget deletion, so this is safe from the signal).
        self._rebuild_ui()
        self._apply_titlebar_theme()
        # And the popup itself (header, search placeholder, menus) if it's open.
        self._apply_to_app(full=True)

    def _section_appearance(self) -> QWidget:
        C = self.C
        w = QWidget(self); w.setStyleSheet(f"background:{C['bg']};")
        lay = QVBoxLayout(w); lay.setContentsMargins(0,8,0,8); lay.setSpacing(6)

        lay.addWidget(self._heading("🎨  " + i18n.tr("Appearance")))

        # Theme toggle
        theme_row = QWidget(w); theme_row.setStyleSheet(f"background:{C['bg']};")
        tr = QHBoxLayout(theme_row); tr.setContentsMargins(0,0,0,0); tr.setSpacing(8)
        lbl = QLabel(i18n.tr("Theme:"), w); lbl.setFixedWidth(80)
        lbl.setStyleSheet(f"color:{C['text']};background:transparent;")
        tr.addWidget(lbl)

        self._dark_btn  = QPushButton("🌙  " + i18n.tr("Dark"),  w)
        self._light_btn = QPushButton("☀️  " + i18n.tr("Light"), w)
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
        lbl2 = QLabel(i18n.tr("Popup transparency:"), w)
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
        hlbl = QLabel(i18n.tr("Row hover:"), w); hlbl.setFixedWidth(80)
        hlbl.setStyleSheet(f"color:{C['text']};background:transparent;")
        hr.addWidget(hlbl)
        self._hover_colour = self.history.settings.get("hover_colour", "rose")
        self._hover_swatches = {}
        for key, name, swatch in self.HOVER_CHOICES:
            b = QPushButton("", hv_row)
            b.setFixedSize(22, 22)
            b.setCursor(Qt.CursorShape.PointingHandCursor)
            b.setToolTip(i18n.tr(name))
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
         "Right-click twice quickly to open Stacka at the cursor. "
         "One hand, never covers the app's own menu."),
        ("middle", "🖱  Middle-click",
         "Press the scroll wheel to open Stacka. One hand, no menu flash. "
         "Overrides middle-click's usual open-in-new-tab / autoscroll."),
        ("side", "⏪  Mouse side button",
         "Use a thumb Back/Forward button to open Stacka. "
         "Needs a mouse with side buttons."),
        ("ctrl_right", "⌨  Ctrl + right-click",
         "Hold Ctrl and right-click to open Stacka. Plain right-click "
         "stays normal. No menu flash."),
        ("button", "🔘  Overlay button",
         "A “Paste from Stacka” button appears beside the cursor on "
         "every right-click."),
        ("hotkey", "⌨  Hotkey only",
         "No mouse trigger — open Stacka only with your keyboard "
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
        hl.addWidget(self._heading("📐  " + i18n.tr("Sizing")))
        hint = QLabel(i18n.tr("10% steps · 100% = default"), head)
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

            name = QLabel(i18n.tr(label), row); name.setFixedWidth(88)
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
        name = QLabel(i18n.tr("Side list rows"), row); name.setFixedWidth(88)
        name.setStyleSheet(f"color:{C['text']};background:transparent;")
        rl.addWidget(name)
        rows = max(1, min(20, int(self.history.settings.get("side_list_rows", 20))))
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
        fname = QLabel(i18n.tr("Font size"), frow); fname.setFixedWidth(88)
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
        ("default", "🎨  Default Stacka",
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

        lay.addWidget(self._heading("🖼️  " + i18n.tr("Icon pack")))
        self._icon_pack = self.history.settings.get("icon_pack", "default")
        self._icon_pack_btns = {}
        for pack, label, caption in self.ICON_PACKS:
            row = QWidget(w); row.setStyleSheet(f"background:{C['bg']};")
            rl = QHBoxLayout(row); rl.setContentsMargins(0,0,0,0); rl.setSpacing(8)
            btn = QPushButton(i18n.tr(label), row)
            btn.setFixedWidth(165)
            btn.clicked.connect(lambda _=False, p=pack: self._set_icon_pack(p))
            rl.addWidget(btn)
            cap = QLabel(i18n.tr(caption), row); cap.setWordWrap(True)
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

        lay.addWidget(self._heading("🖱️  " + i18n.tr("Popup trigger")))
        hint = QLabel(i18n.tr("Pick up to two — e.g. overlay button + double "
                              "right-click. “Hotkey only” can’t be combined."), w)
        hint.setWordWrap(True)
        hint.setStyleSheet(f"color:{C['text_dim']};font-size:8pt;"
                           f"background:transparent;")
        lay.addWidget(hint)

        # Store build: Windows virtualizes a packaged app's registry, so the
        # "Paste from Stacka" entry can't be added to Explorer's own menu.
        # Say so here — otherwise it just looks like a missing feature.
        if app_paths.is_packaged():
            note = QLabel(i18n.tr(
                "Note: the Windows Explorer right-click entry isn't available "
                "in the Microsoft Store version. Use one of the triggers below "
                "— they all work in Explorer too."), w)
            note.setWordWrap(True)
            note.setStyleSheet(f"color:{C['accent_hover']};font-size:8pt;"
                               f"background:transparent;")
            lay.addWidget(note)
        self._triggers = self._read_triggers()
        self._trigger_btns = {}

        for mode, label, caption in self.TRIGGER_MODES:
            row = QWidget(w); row.setStyleSheet(f"background:{C['bg']};")
            rl = QHBoxLayout(row); rl.setContentsMargins(0,0,0,0); rl.setSpacing(8)
            btn = QPushButton(i18n.tr(label), row)
            btn.setFixedWidth(165)
            btn.clicked.connect(lambda _=False, m=mode: self._toggle_trigger(m))
            rl.addWidget(btn)
            cap = QLabel(i18n.tr(caption), row)
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

        lay.addWidget(self._heading("🪟  " + i18n.tr("Close behaviour")))
        self._close_mode = self.history.settings.get("close_mode", "click")

        def option_row(label, mode, caption):
            row = QWidget(w); row.setStyleSheet(f"background:{C['bg']};")
            rl = QHBoxLayout(row); rl.setContentsMargins(0,0,0,0); rl.setSpacing(8)
            btn = QPushButton(i18n.tr(label), row)
            btn.setFixedWidth(140)
            btn.clicked.connect(lambda _=False, m=mode: self._set_close_mode(m))
            rl.addWidget(btn)
            cap = QLabel(i18n.tr(caption), row)
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

        lay.addWidget(self._heading("⌨️  " + i18n.tr("Shortcuts")))
        row = QWidget(w); row.setStyleSheet(f"background:{C['bg']};")
        rl = QHBoxLayout(row); rl.setContentsMargins(0,0,0,0); rl.setSpacing(8)
        btn = QPushButton(i18n.tr("Manage Shortcuts…"), row)
        btn.setFixedWidth(150)
        btn.setStyleSheet(_btn_style(C["accent"], C["accent_hover"]))
        btn.clicked.connect(self._open_shortcuts)
        rl.addWidget(btn)
        cur = self.history.settings.get("hotkey_open", "ctrl+shift+v")
        cap = QLabel(f"{i18n.tr('Launch Stacka:')}  {cur.upper()}", row)
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

        lay.addWidget(self._heading("🗂   " + i18n.tr("History")))

        row = QWidget(w); row.setStyleSheet(f"background:{C['bg']};")
        rl = QHBoxLayout(row); rl.setContentsMargins(0,0,0,0); rl.setSpacing(8)
        lbl = QLabel(i18n.tr("History size limit:"), row)
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
        lbl2 = QLabel(i18n.tr("items"), row); lbl2.setStyleSheet(f"color:{C['text_dim']};background:transparent;")
        rl.addWidget(lbl2)
        rl.addStretch()
        lay.addWidget(row)

        btn_row = QWidget(w); btn_row.setStyleSheet(f"background:{C['bg']};")
        bl = QHBoxLayout(btn_row); bl.setContentsMargins(0,0,0,0); bl.setSpacing(8)
        save_btn = QPushButton(i18n.tr("Save Limit"), btn_row)
        save_btn.setFixedWidth(100)
        save_btn.setStyleSheet(_btn_style(C["accent"], C["accent_hover"]))
        save_btn.clicked.connect(self._save_limit)
        bl.addWidget(save_btn)
        self._save_feedback = QLabel("", btn_row)
        self._save_feedback.setStyleSheet(f"color:{C['success']};background:transparent;")
        bl.addWidget(self._save_feedback)
        bl.addStretch()
        lay.addWidget(btn_row)

        # ── Auto-wipe ─────────────────────────────────────────────────────────
        # Scheduled clear-out so old clips don't pile up forever. Pinned items
        # are always kept — pinning means "never remove this automatically".
        wipe_row = QWidget(w); wipe_row.setStyleSheet(f"background:{C['bg']};")
        wl = QHBoxLayout(wipe_row); wl.setContentsMargins(0,0,0,0); wl.setSpacing(8)
        wlbl = QLabel(i18n.tr("Auto-wipe:"), wipe_row)
        wlbl.setStyleSheet(f"color:{C['text']};background:transparent;")
        wl.addWidget(wlbl)

        self._wipe_combo = QComboBox(wipe_row)
        for key, label, _days in auto_wipe.SCHEDULES:
            self._wipe_combo.addItem(i18n.tr(label), key)
        cur = self.history.settings.get("auto_wipe", auto_wipe.OFF)
        idx = self._wipe_combo.findData(cur)
        if idx >= 0:
            self._wipe_combo.setCurrentIndex(idx)   # before connect — no stray fire
        self._wipe_combo.setFixedWidth(130)
        self._wipe_combo.setCursor(Qt.CursorShape.PointingHandCursor)
        self._wipe_combo.setStyleSheet(
            f"QComboBox{{background:{C['bg_input']};color:{C['text']};border:1px solid "
            f"{C['border']};border-radius:4px;padding:3px 8px;}}"
            "QComboBox::drop-down{subcontrol-origin:padding;subcontrol-position:center right;"
            "border:none;width:20px;}"
            f"QComboBox::down-arrow{{width:0;height:0;margin-right:7px;"
            "border-left:5px solid transparent;border-right:5px solid transparent;"
            f"border-top:6px solid {C['text_dim']};}}"
            f"QComboBox QAbstractItemView{{background:{C['bg_section']};color:{C['text']};"
            f"selection-background-color:{C['accent']};selection-color:white;outline:none;}}")
        self._wipe_combo.currentIndexChanged.connect(self._on_auto_wipe_changed)
        wl.addWidget(self._wipe_combo)
        wl.addStretch()
        lay.addWidget(wipe_row)

        self._wipe_hint = QLabel("", w)
        self._wipe_hint.setWordWrap(True)
        self._wipe_hint.setStyleSheet(
            f"color:{C['text_dim']};font-size:8pt;background:transparent;")
        lay.addWidget(self._wipe_hint)
        self._refresh_wipe_hint()

        clear_btn = QPushButton("🧹  " + i18n.tr("Clear All History"), w)
        clear_btn.setStyleSheet(_btn_style(C["danger"], C["danger_hover"]))
        clear_btn.clicked.connect(self._confirm_clear)
        lay.addWidget(clear_btn)
        return w

    def _refresh_wipe_hint(self):
        """One line under the dropdown: what it will do and when."""
        s = self.history.settings
        key = s.get("auto_wipe", auto_wipe.OFF)
        if key == auto_wipe.OFF:
            self._wipe_hint.setText(
                i18n.tr("History is kept until you clear it yourself."))
            return
        due = auto_wipe.next_due(s)
        when = due.strftime("%d %b %Y") if due else "—"
        self._wipe_hint.setText(
            f"{i18n.tr('Clears every list automatically. Pinned items are kept.')} "
            f"{i18n.tr('Next:')} {when}")

    def _on_auto_wipe_changed(self, idx: int):
        key = self._wipe_combo.itemData(idx)
        if key is None or key == self.history.settings.get("auto_wipe", auto_wipe.OFF):
            return
        # start_schedule stamps "now", so a freshly chosen schedule counts from
        # today instead of firing immediately.
        auto_wipe.start_schedule(self.history, key)
        self._refresh_wipe_hint()

    def _section_profiles(self) -> QWidget:
        C = self.C
        w = QWidget(self); w.setStyleSheet(f"background:{C['bg']};")
        lay = QVBoxLayout(w); lay.setContentsMargins(0,8,0,8); lay.setSpacing(6)

        lay.addWidget(self._heading("👤  " + i18n.tr("Profiles")))
        sub = QLabel(i18n.tr("Organise your clipboard into named workflow collections."), w)
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

        lay.addWidget(self._heading("ℹ️   " + i18n.tr("About Stacka")))
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

        # Link rows — Source = this repo (issues, code, licence, releases),
        # Developer = the profile where the rest of Cosmas's projects live.
        def _link_row(label, url):
            row = QWidget(w); row.setStyleSheet(f"background:{C['bg']};")
            rl = QHBoxLayout(row); rl.setContentsMargins(0,0,0,0)
            lbl = QLabel(label, row)
            lbl.setFixedWidth(80)
            lbl.setStyleSheet(f"color:{C['text_dim']};background:transparent;")
            link = QLabel(f'<a href="{url}" style="color:{C["accent_hover"]};">{url}</a>', row)
            link.setOpenExternalLinks(True)
            link.setTextFormat(Qt.TextFormat.RichText)
            link.setStyleSheet("background:transparent;")
            rl.addWidget(lbl); rl.addWidget(link); rl.addStretch()
            lay.addWidget(row)

        _link_row("Source:", GITHUB_URL)
        _link_row("Developer:", GITHUB_PROFILE_URL)

        # STORE BUILD: no Support/donation button. This is the paid Store
        # edition — a paying customer should not also be asked to donate.
        # The free build on the other branches keeps it here.
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
            popup = QApplication.instance().property("stacka_popup")
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
            popup = QApplication.instance().property("stacka_popup")
            if popup is not None and getattr(popup, "_popup", None):
                popup._popup.setWindowOpacity(opacity)
        except Exception:
            pass

    # ── History ───────────────────────────────────────────────────────────────

    def _save_limit(self):
        try:
            value = int(self._limit_edit.text())
            if not (1 <= value <= 1000):
                self._tell("Invalid Value",
                    "History limit must be between 1 and 1000.")
                return
            self.history.set_limit(value)
            # Same universal limit applies to every profile — each trims its
            # own copies independently.
            self.profiles.enforce_all_limits()
            self._save_feedback.setText("✓  Saved!")
            QTimer.singleShot(2000, lambda: self._save_feedback.setText(""))
        except ValueError:
            self._tell("Invalid Value",
                "Please enter a whole number.")

    # ── Themed dialogs ────────────────────────────────────────────────────────
    # QMessageBox does NOT inherit this window's stylesheet, so on the dark
    # theme it rendered dark text on a dark button — the Yes/No buttons were
    # all but invisible. Every confirmation goes through these helpers.

    def _style_box(self, box: QMessageBox):
        C = self.C
        box.setStyleSheet(
            f"QMessageBox {{background:{C['bg']};}}"
            f"QMessageBox QLabel {{color:{C['text']};background:transparent;"
            "font-family:'Segoe UI';font-size:10pt;}"
            "QMessageBox QPushButton {"
            f"background:{C['accent']};color:white;border:1px solid "
            f"{_shade(C['accent'], -0.25)};border-radius:5px;"
            "padding:6px 18px;min-width:76px;font-family:'Segoe UI';font-size:9pt;}"
            f"QMessageBox QPushButton:hover {{background:{C['accent_hover']};}}"
            f"QMessageBox QPushButton:pressed {{background:{_shade(C['accent'], -0.2)};}}")
        return box

    def _ask(self, title: str, text: str) -> bool:
        """Yes/No confirmation. Defaults to No so Enter can't destroy data."""
        box = QMessageBox(self)
        box.setIcon(QMessageBox.Icon.Question)
        box.setWindowTitle(title)
        box.setText(text)
        box.setStandardButtons(QMessageBox.StandardButton.Yes |
                               QMessageBox.StandardButton.No)
        box.setDefaultButton(QMessageBox.StandardButton.No)
        self._style_box(box)
        return box.exec() == QMessageBox.StandardButton.Yes

    def _tell(self, title: str, text: str):
        box = QMessageBox(self)
        box.setIcon(QMessageBox.Icon.Information)
        box.setWindowTitle(title)
        box.setText(text)
        box.setStandardButtons(QMessageBox.StandardButton.Ok)
        self._style_box(box)
        box.exec()

    def _confirm_clear(self):
        n_prof = 0
        if self.profiles:
            n_prof = len([p for p in self.profiles.get_all_profiles()
                          if p["id"] != "general"])
        extra = (f"\n\nThis empties General and all {n_prof} profile(s), "
                 "including pinned items." if n_prof else
                 "\n\nThis empties everything, including pinned items.")
        if self._ask(i18n.tr("Clear All History"),
                     i18n.tr("Clear your entire clipboard history?") + extra +
                     "\n\n" + i18n.tr("This cannot be undone.")):
            self.history.clear_all()
            if self.profiles:
                self.profiles.clear_all_profiles()
                self._refresh_profile_list()
            self._apply_to_app()
            self._tell(i18n.tr("Done"),
                       i18n.tr("Clipboard history has been cleared."))

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
            self._tell("Switch Profile",
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
            self._tell("Rename", "Select a profile first."); return
        if p.get("built_in"):
            self._tell("Rename", "General cannot be renamed."); return
        name, ok = QInputDialog.getText(self, "Rename Profile",
            f"New name for '{p['name']}':", text=p["name"])
        if ok and name.strip():
            self.profiles.rename_profile(p["id"], name.strip())
            self._refresh_profile_list()

    def _delete_profile(self):
        p = self._selected_profile()
        if not p:
            self._tell("Delete", "Select a profile first."); return
        if p.get("built_in"):
            self._tell("Delete", "General cannot be deleted."); return
        if self._ask("Delete Profile",
                     f"Delete the profile '{p['name']}'?\n\n"
                     "Its own copies of the clips are deleted with it. General "
                     "and your other profiles are not affected.\n\n"
                     "This cannot be undone."):
            self.profiles.delete_profile(p["id"])
            self._refresh_profile_list()

    def _clear_selected_profile(self):
        p = self._selected_profile()
        if not p:
            self._tell("Clear", "Select a profile first."); return
        # Wording follows the EXPORT model: every list owns its items, so
        # clearing one list never touches another. (The old text said things
        # like "Others are permanently deleted" and "Items stay in General",
        # which described the shared-pool design this app no longer uses —
        # and was simply wrong for a profile's own copies.)
        if p["id"] == "general":
            if self._ask("Clear General",
                         "Clear all items from General?\n\n"
                         "Your profiles keep their own copies and are not "
                         "affected.\n\nThis cannot be undone."):
                self.history.clear_all()
                self._refresh_profile_list()
                self._apply_to_app()
                self._tell("Done", "General has been cleared.")
        else:
            if self._ask("Clear Profile",
                         f"Clear all items from '{p['name']}'?\n\n"
                         "Only this profile's own copies are removed. General "
                         "and your other profiles are not affected.\n\n"
                         "This cannot be undone."):
                self.profiles.clear_profile(p["id"])
                self._refresh_profile_list()
                self._apply_to_app()
                self._tell("Done", f"'{p['name']}' has been cleared.")

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
