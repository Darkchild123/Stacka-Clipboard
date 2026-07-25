# ============================================================
# ClipDrop - tray_icon.py  (PyQt6 rewrite)
# ============================================================
# System tray icon using QSystemTrayIcon.
# Gives the user quick access to settings and controls
# from the Windows taskbar notification area.
# ============================================================

import os
import sys
import threading

from PIL import Image, ImageDraw

from PyQt6.QtWidgets import QSystemTrayIcon, QMenu, QApplication
from PyQt6.QtGui     import QIcon, QPixmap, QImage, QAction
from PyQt6.QtCore    import Qt, QTimer, pyqtSignal, QObject

from app_paths import resource_path
import i18n

ICON_PATH = resource_path("assets", "icon.png")


def _pil_to_qpixmap(pil_img: Image.Image) -> QPixmap:
    img  = pil_img.convert("RGBA")
    data = img.tobytes("raw", "RGBA")
    qimg = QImage(data, img.width, img.height, QImage.Format.Format_RGBA8888)
    return QPixmap.fromImage(qimg)


class TrayIcon:

    def __init__(self, history_manager, profile_manager, root=None):
        self.history  = history_manager
        self.profiles = profile_manager
        # root is unused in Qt but kept for API compatibility
        self._tray         = None
        self._icon_img     = self._load_icon()
        self._settings_win = None   # keep reference — prevents GC crash

    def start(self):
        """Called from the main thread — creates the tray icon immediately."""
        self._create_tray()
        print("Tray icon started.")

    def stop(self):
        if self._tray:
            self._tray.hide()

    # ── Create tray ──────────────────────────────────────────────────────────

    def _create_tray(self):
        # Prefer the multi-size .ico (crisp at the small tray sizes); fall back
        # to the PIL-loaded icon.png / generated placeholder.
        ico = resource_path("assets", "clipdrop.ico")
        if os.path.exists(ico):
            icon = QIcon(ico)
        else:
            icon = QIcon(_pil_to_qpixmap(self._icon_img))

        self._tray = QSystemTrayIcon(icon)
        self._tray.setToolTip("ClipDrop")
        self._tray.activated.connect(self._on_tray_activated)

        menu = QMenu()
        menu.setStyleSheet("""
            QMenu { background:#1e1e2e; color:#e2e8f0; font-family:'Segoe UI';
                    font-size:9pt; border:1px solid #3f3f5f; }
            QMenu::item:selected { background:#4c4c8a; }
        """)

        # Header (disabled label)
        header = menu.addAction("ClipDrop")
        header.setEnabled(False)
        menu.addSeparator()

        # Active profile (dynamic, refreshed on open)
        self._profile_action = menu.addAction(self._profile_label())
        self._profile_action.setEnabled(False)
        menu.addSeparator()

        settings_act = menu.addAction("⚙  " + i18n.tr("Settings"))
        settings_act.triggered.connect(self._open_settings)

        clear_act = menu.addAction("🧹 " + i18n.tr("Clear History"))
        clear_act.triggered.connect(self._clear_history)
        menu.addSeparator()

        quit_act = menu.addAction("✖  " + i18n.tr("Quit ClipDrop"))
        quit_act.triggered.connect(self._quit)

        # Refresh profile label each time menu opens
        menu.aboutToShow.connect(self._refresh_profile_action)

        self._tray.setContextMenu(menu)
        self._tray.show()

    def _profile_label(self) -> str:
        try:
            return f"{i18n.tr('Profile:')} {self.profiles.get_active_profile()['name']}"
        except Exception:
            return f"{i18n.tr('Profile:')} General"

    def _refresh_profile_action(self):
        if self._profile_action:
            self._profile_action.setText(self._profile_label())

    # ── Tray activated ───────────────────────────────────────────────────────

    def _on_tray_activated(self, reason):
        if reason == QSystemTrayIcon.ActivationReason.DoubleClick:
            self._open_settings()

    # ── Menu actions ─────────────────────────────────────────────────────────

    def _open_settings(self):
        from settings_panel import SettingsPanel
        # Store on self — prevents Python GC from destroying the panel while
        # it is still open, which would crash on any user interaction.
        if self._settings_win and self._settings_win.isVisible():
            self._settings_win.raise_()
            self._settings_win.activateWindow()
            return
        self._settings_win = SettingsPanel(self.history, self.profiles)
        self._settings_win.show()

    def _clear_history(self):
        self.history.clear_all()
        print("History cleared from tray menu.")
        if self._tray:
            self._tray.showMessage(
                "ClipDrop",
                i18n.tr("Clipboard history has been cleared."),
                QSystemTrayIcon.MessageIcon.Information,
                2000
            )

    def _quit(self):
        print("Quitting ClipDrop...")
        # Dismiss any open context menu + the popup/side panels FIRST, so
        # nothing is left orphaned on screen after the event loop stops.
        try:
            pw = QApplication.activePopupWidget()
            while pw is not None:
                pw.close()
                nxt = QApplication.activePopupWidget()
                if nxt is pw:
                    break            # not going away — avoid a spin
                pw = nxt
            popup = QApplication.instance().property("clipdrop_popup")
            if popup is not None:
                popup._do_hide()
        except Exception:
            pass
        if self._tray:
            self._tray.hide()
        QApplication.quit()

    # ── Icon loading ─────────────────────────────────────────────────────────

    def _load_icon(self) -> Image.Image:
        if os.path.exists(ICON_PATH):
            return Image.open(ICON_PATH)
        print("No icon found in assets/. Using generated placeholder.")
        return self._generate_placeholder_icon()

    def _generate_placeholder_icon(self) -> Image.Image:
        size  = 64
        image = Image.new("RGBA", (size, size), (0, 0, 0, 0))
        draw  = ImageDraw.Draw(image)
        draw.rounded_rectangle([4, 4, size-4, size-4], radius=12, fill=(79, 70, 229))
        draw.text((size//2, size//2), "CD", fill=(255,255,255), anchor="mm")
        return image
