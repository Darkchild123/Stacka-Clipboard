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
)
from PyQt6.QtCore    import Qt, QTimer, QEvent
from PyQt6.QtGui     import QFont, QIntValidator, QCursor

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


def _btn_style(bg: str, hover: str, fg: str = "white") -> str:
    return (f"QPushButton {{background:{bg};color:{fg};"
            f"font-family:'Segoe UI';font-size:9pt;"
            f"padding:5px 12px;border-radius:4px;border:none;}}"
            f"QPushButton:hover {{background:{hover};}}")


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

        # Install global event filter for click-outside-to-close
        QApplication.instance().installEventFilter(self)

    # ── Click-outside-to-close ────────────────────────────────────────────────

    def eventFilter(self, obj, event):
        # A minimized window is still isVisible() in Qt terms — clicking
        # another ClipDrop window must not close a minimized settings panel.
        if (event.type() == QEvent.Type.MouseButtonPress
                and self.isVisible() and not self.isMinimized()):
            try:
                gpos = event.globalPosition().toPoint()
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

        # Header
        hdr = QLabel("📋  ClipDrop Settings", self)
        hdr.setFont(QFont("Segoe UI", 13, QFont.Weight.Bold))
        hdr.setAlignment(Qt.AlignmentFlag.AlignCenter)
        hdr.setFixedHeight(48)
        hdr.setStyleSheet(f"background:{C['accent']};color:white;")
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
        scroll_lay.addWidget(self._section_behaviour())
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
        scroll.setStyleSheet(f"""
            QScrollArea {{background:{C['bg']};border:none;}}
            QScrollBar:vertical {{background:{C['bg']};width:8px;margin:0;}}
            QScrollBar::handle:vertical {{background:{C['border']};
                border-radius:4px;min-height:24px;}}
            QScrollBar::add-line:vertical, QScrollBar::sub-line:vertical {{height:0;}}
            QScrollBar::add-page:vertical, QScrollBar::sub-page:vertical {{background:none;}}
        """)
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
        current_opacity = int(self.history.settings.get("transparency", 1.0) * 100)
        self._slider = QSlider(Qt.Orientation.Horizontal, w)
        self._slider.setRange(40, 100)
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
        return w

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
        self._rebuild_ui()     # this window restyles instantly…
        self._apply_to_app()   # …and so does the open popup

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
        The popup re-reads theme + transparency from settings on every
        rebuild, so a _refresh() re-renders it with the new palette."""
        try:
            popup = QApplication.instance().property("clipdrop_popup")
            if popup is not None and getattr(popup, "_popup", None):
                popup._refresh()
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
                protected = set()
                for prof in self.profiles.get_all_profiles():
                    if not prof.get("built_in"):
                        protected.update(prof.get("item_ids", []))
                to_del = [it for it in list(self.history.items) if it["id"] not in protected]
                for it in to_del:
                    self.history.delete_item(it["id"])
                kept = 0
                for it in self.history.items:
                    if it["id"] in protected:
                        it["hidden"] = True; kept += 1
                if kept:
                    self.history._save_history()
                self._refresh_profile_list()
                QMessageBox.information(self, "Done",
                    f"General cleared.\n{kept} item(s) kept in named profiles.")
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
