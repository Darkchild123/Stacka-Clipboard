# ============================================================
# ClipDrop - snippet_window.py
# ============================================================
# Blank scratchpad opened by the "New snippet" hotkey.
# Type a note or code snippet, hit Save (or Ctrl+S) and it lands
# in the clipboard history like any copied item — pasteable,
# pinnable, assignable to profiles.
# ============================================================

import time
import hashlib

from PyQt6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel,
    QPlainTextEdit, QPushButton, QApplication,
)
from PyQt6.QtCore import Qt
from PyQt6.QtGui  import QFont, QCursor, QKeySequence, QShortcut

from settings_panel import (
    DARK, LIGHT, _btn_style, _grad_v, _shade, _titlebar_dark,
)


class SnippetWindow(QWidget):
    """Blank local scratchpad → saved straight into clipboard history."""

    def __init__(self, history_manager, popup=None, parent=None):
        super().__init__(parent,
                         Qt.WindowType.Window |
                         Qt.WindowType.WindowStaysOnTopHint |
                         Qt.WindowType.WindowCloseButtonHint)
        self.history = history_manager
        self.popup   = popup           # DropdownPopup — for toast + live refresh
        theme        = history_manager.settings.get("theme", "dark")
        self._dark   = theme == "dark"
        self.C       = DARK if self._dark else LIGHT

        self.setWindowTitle("New Snippet")
        self.setFixedSize(460, 320)
        self._build()

        # Centre on the cursor's screen
        screen = QApplication.screenAt(QCursor.pos()) or QApplication.primaryScreen()
        fg = self.frameGeometry()
        fg.moveCenter(screen.availableGeometry().center())
        self.move(fg.topLeft())
        _titlebar_dark(self, self._dark)

    def _build(self):
        C = self.C
        self.setStyleSheet(f"QWidget {{background:{C['bg']};}} "
                           f"QLabel {{color:{C['text']};background:transparent;}}")

        main = QVBoxLayout(self)
        main.setContentsMargins(0, 0, 0, 0)
        main.setSpacing(0)

        hdr = QLabel("✏️  New Snippet", self)
        hdr.setFont(QFont("Segoe UI", 11, QFont.Weight.Bold))
        hdr.setAlignment(Qt.AlignmentFlag.AlignCenter)
        hdr.setFixedHeight(40)
        hdr.setStyleSheet(
            f"background:{_grad_v(C['accent_hover'], _shade(C['accent'], -0.18))};"
            f"color:white;border-bottom:1px solid rgba(0,0,0,90);")
        main.addWidget(hdr)

        body = QVBoxLayout()
        body.setContentsMargins(12, 10, 12, 10)
        body.setSpacing(8)

        self._edit = QPlainTextEdit(self)
        self._edit.setPlaceholderText(
            "Type a note or code snippet…\nCtrl+S saves it to your clipboard history.")
        self._edit.setFont(QFont("Consolas", 10))
        self._edit.setStyleSheet(f"""
            QPlainTextEdit {{background:{C['bg_input']};color:{C['text']};
            border:1px solid {C['border']};border-radius:6px;padding:6px;}}
        """)
        body.addWidget(self._edit, 1)

        foot = QHBoxLayout()
        foot.setSpacing(8)
        foot.addStretch()
        save = QPushButton("💾  Save", self)
        save.setFixedWidth(110)
        save.setStyleSheet(_btn_style(C["accent"], C["accent_hover"]))
        save.clicked.connect(self._save)
        foot.addWidget(save)
        cancel = QPushButton("Cancel", self)
        cancel.setFixedWidth(90)
        cancel.setStyleSheet(_btn_style(C["bg_section"], C["accent"], C["text_dim"]))
        cancel.clicked.connect(self.close)
        foot.addWidget(cancel)
        body.addLayout(foot)

        main.addLayout(body)

        QShortcut(QKeySequence("Ctrl+S"), self).activated.connect(self._save)
        self._edit.setFocus()

    # ── Save ─────────────────────────────────────────────────────────────────

    def _save(self):
        text = self._edit.toPlainText().strip()
        if not text:
            self.close()
            return

        # Classify like the clipboard watcher would (code / hex / url / text)
        itype = "text"
        watcher = getattr(self.popup, "watcher", None) if self.popup else None
        if watcher is not None:
            try:
                itype = watcher._classify_text(text)
            except Exception:
                pass

        item = {
            "id":      hashlib.md5(text.encode("utf-8", errors="ignore")).hexdigest(),
            "type":    itype,
            "content": text,
            "source":  "Snippet",
            "pinned":  False,
        }
        self.history.add_item(item)

        if self.popup is not None:
            self.popup._refresh()      # live update if the popup is open
            self.popup._show_toast("Snippet saved")
        self.close()
