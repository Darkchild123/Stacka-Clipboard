# ============================================================
# ClipDrop - settings_panel.py  (PyQt6 rewrite)
# ============================================================
# Settings window — lets the user control ClipDrop behaviour.
# Opened from the system tray icon menu.
# ============================================================

import webbrowser

from PyQt6.QtWidgets import (
    QDialog, QWidget, QVBoxLayout, QHBoxLayout,
    QLabel, QLineEdit, QPushButton, QSlider,
    QListWidget, QListWidgetItem, QFrame,
    QInputDialog, QMessageBox, QApplication,
)
from PyQt6.QtCore    import Qt, QTimer
from PyQt6.QtGui     import QFont, QIntValidator

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


class SettingsPanel(QDialog):

    def __init__(self, history_manager, profile_manager=None, parent=None):
        super().__init__(parent, Qt.WindowType.WindowStaysOnTopHint)
        self.history  = history_manager
        self.profiles = profile_manager
        self._theme   = history_manager.settings.get("theme", "dark")
        self.C        = DARK if self._theme == "dark" else LIGHT

        self.setWindowTitle("ClipDrop Settings")
        self.setFixedWidth(420)
        self.setWindowOpacity(history_manager.settings.get("transparency", 1.0))

        self._build()

        # Centre on screen at 68%, 15%
        screen = QApplication.primaryScreen().geometry()
        self.move(int(screen.width()*0.68), int(screen.height()*0.15))

    def _build(self):
        C = self.C
        self.setStyleSheet(f"QDialog {{background:{C['bg']};}} "
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

        # Scroll area
        scroll_w = QWidget()
        scroll_w.setStyleSheet(f"background:{C['bg']};")
        scroll_lay = QVBoxLayout(scroll_w)
        scroll_lay.setContentsMargins(16, 8, 16, 8)
        scroll_lay.setSpacing(0)

        scroll_lay.addWidget(self._section_appearance())
        scroll_lay.addWidget(self._divider())
        scroll_lay.addWidget(self._section_history())
        if self.profiles:
            scroll_lay.addWidget(self._divider())
            scroll_lay.addWidget(self._section_profiles())
        scroll_lay.addWidget(self._divider())
        scroll_lay.addWidget(self._section_info())
        scroll_lay.addStretch()

        main.addWidget(scroll_w)

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
            ("＋ New",    self._new_profile,    False),
            ("✎ Rename",  self._rename_profile, False),
            ("✕ Delete",  self._delete_profile, False),
        ]))
        lay.addWidget(btn_row([
            ("↑ Move Up",   self._move_profile_up,        False),
            ("↓ Move Down", self._move_profile_down,      False),
            ("🧹 Clear",    self._clear_selected_profile, True),
        ]))
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
        self._theme = theme
        self.C = DARK if theme == "dark" else LIGHT
        self.history.save_setting("theme", theme)
        self._refresh_theme_buttons()

    # ── Opacity ───────────────────────────────────────────────────────────────

    def _on_opacity_change(self, value: int):
        opacity = value / 100.0
        self.setWindowOpacity(opacity)
        self._opacity_lbl.setText(f"{value}%")
        self.history.save_setting("transparency", opacity)

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
