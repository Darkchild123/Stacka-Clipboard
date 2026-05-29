# ============================================================
# ClipDrop - dropdown_popup.py  (PyQt6 rewrite)
# ============================================================
# The main visual interface of ClipDrop.
# Shows a popup list at the cursor with all clipboard items.
#
# Framework: PyQt6
# Key design decisions:
#   - QWidget with FramelessWindowHint — no title bar, no focus steal
#   - WS_EX_NOACTIVATE applied via win32gui so keyboard focus stays
#     in the target app through the entire paste operation
#   - QListWidget drives the item list — real-time in-place updates
#     via takeItem/insertItem (no destroy/rebuild, no flicker)
#   - QTimer replaces root.after() for thread-safe scheduling
#   - Signals/slots replace tkinter's fragile binding system
# ============================================================

import os
import io
import time
import struct
import hashlib

import win32clipboard
import win32con
import win32gui
import pyautogui

from PIL import Image

from PyQt6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel, QLineEdit,
    QListWidget, QListWidgetItem, QScrollArea, QFrame,
    QAbstractItemView, QMenu, QApplication, QSizePolicy,
    QGraphicsOpacityEffect,
)
from PyQt6.QtCore import (
    Qt, QTimer, QPoint, QSize, QRect, QPropertyAnimation,
    QEasingCurve, pyqtSignal, QObject, pyqtSlot,
)
from PyQt6.QtGui import (
    QColor, QPainter, QPen, QBrush, QFont, QFontMetrics,
    QPixmap, QImage, QCursor, QIcon, QPalette,
)

# ── Colour themes ────────────────────────────────────────────────────────────

DARK = {
    "bg":           "#1e1e2e",
    "bg_item":      "#2a2a3e",
    "bg_hover":     "#4c4c8a",
    "bg_pinned":    "#2d3748",
    "accent":       "#4f46e5",
    "accent_light": "#6366f1",
    "text":         "#e2e8f0",
    "text_dim":     "#94a3b8",
    "text_preview": "#cbd5e1",
    "danger":       "#ef4444",
    "pin":          "#f59e0b",
    "border":       "#3f3f5f",
}

LIGHT = {
    "bg":           "#f8fafc",
    "bg_item":      "#f1f5f9",
    "bg_hover":     "#e2e8f0",
    "bg_pinned":    "#dbeafe",
    "accent":       "#4f46e5",
    "accent_light": "#6366f1",
    "text":         "#1e293b",
    "text_dim":     "#64748b",
    "text_preview": "#334155",
    "danger":       "#ef4444",
    "pin":          "#d97706",
    "border":       "#cbd5e1",
}

TYPE_COLOURS = {
    "text":   "#4f46e5",
    "url":    "#0ea5e9",
    "file":   "#f59e0b",
    "folder": "#f59e0b",
    "code":   "#7c3aed",
    "bash":   "#16a34a",
    "image":  "#0891b2",
}

_FILE_TYPE_MAP = {}
for _e in ['.png','.jpg','.jpeg','.gif','.bmp','.webp','.ico','.tiff','.tif','.heic','.avif','.svg']:
    _FILE_TYPE_MAP[_e] = "image"
for _e in ['.mp4','.mov','.avi','.mkv','.wmv','.flv','.webm','.m4v','.mpg','.mpeg','.3gp','.ts']:
    _FILE_TYPE_MAP[_e] = "video"
for _e in ['.mp3','.wav','.flac','.aac','.ogg','.m4a','.wma','.opus','.aiff']:
    _FILE_TYPE_MAP[_e] = "audio"
for _e in ['.xlsx','.xls','.xlsm','.ods','.numbers','.csv','.tsv']:
    _FILE_TYPE_MAP[_e] = "excel"
for _e in ['.docx','.doc','.odt','.rtf','.pages']:
    _FILE_TYPE_MAP[_e] = "word"
for _e in ['.pptx','.ppt','.odp','.key']:
    _FILE_TYPE_MAP[_e] = "ppt"
for _e in ['.pdf']:
    _FILE_TYPE_MAP[_e] = "pdf"
for _e in ['.exe','.msi','.apk','.dmg','.deb','.rpm','.jar']:
    _FILE_TYPE_MAP[_e] = "exe"
for _e in ['.zip','.rar','.7z','.tar','.gz','.bz2','.xz','.cab','.iso']:
    _FILE_TYPE_MAP[_e] = "zip"
for _e in ['.html','.htm','.xhtml','.php','.asp','.aspx','.jsp']:
    _FILE_TYPE_MAP[_e] = "html"
for _e in ['.py','.js','.ts','.jsx','.tsx','.java','.c','.cpp','.h','.cs',
           '.go','.rs','.rb','.swift','.kt','.r','.sql','.css','.scss',
           '.vue','.svelte','.lua','.bat','.cmd','.sh','.bash','.ps1']:
    _FILE_TYPE_MAP[_e] = "code"
for _e in ['.txt','.md','.log','.ini','.cfg','.conf','.json','.xml','.yaml','.yml','.toml']:
    _FILE_TYPE_MAP[_e] = "text"


# ── Helpers ──────────────────────────────────────────────────────────────────

def _qc(hex_str: str) -> QColor:
    return QColor(hex_str)

def _hex_lerp(c1: str, c2: str, t: float) -> str:
    t = max(0.0, min(1.0, t))
    r1,g1,b1 = int(c1[1:3],16), int(c1[3:5],16), int(c1[5:7],16)
    r2,g2,b2 = int(c2[1:3],16), int(c2[3:5],16), int(c2[5:7],16)
    return "#{:02x}{:02x}{:02x}".format(
        int(r1+(r2-r1)*t), int(g1+(g2-g1)*t), int(b1+(b2-b1)*t))

def _set_no_activate(hwnd: int):
    """Apply WS_EX_NOACTIVATE so the window never steals keyboard focus."""
    try:
        ex = win32gui.GetWindowLong(hwnd, win32con.GWL_EXSTYLE)
        win32gui.SetWindowLong(hwnd, win32con.GWL_EXSTYLE,
                               ex | win32con.WS_EX_NOACTIVATE)
    except Exception:
        pass

def _icon_pixmap(icon_type: str, size: int = 32) -> QPixmap:
    """Return a QPixmap for the given icon type, using PIL to draw it."""
    from PIL import ImageDraw
    img = Image.new("RGBA", (size, size), (0, 0, 0, 0))
    d   = ImageDraw.Draw(img)

    if icon_type == "text":
        d.rounded_rectangle([1,1,size-1,size-1], radius=5, fill="#4f46e5")
        lw = max(1, size//8)
        for i, y in enumerate([8, 14, 20]):
            w2 = size-8 if i == 2 else size-5
            d.rectangle([4, y, w2, y+lw], fill="white")
    elif icon_type == "url":
        d.rounded_rectangle([1,1,size-1,size-1], radius=6, fill="#0ea5e9")
        lw=3
        d.rounded_rectangle([13,15,size-2,size-5], radius=5, fill="white")
        d.rounded_rectangle([13+lw,15+lw,size-2-lw,size-5-lw], radius=3, fill="#0ea5e9")
        d.rounded_rectangle([2,5,22,19], radius=5, fill="white")
        d.rounded_rectangle([2+lw,5+lw,22-lw,19-lw], radius=3, fill="#0ea5e9")
    elif icon_type == "image":
        d.rounded_rectangle([1,1,size-1,size-1], radius=5, fill="#0891b2")
        d.ellipse([5,5,13,13], fill="#fef9c3")
        d.polygon([(3,size-5),(size//2,12),(size-3,size-5)], fill="#164e63")
    elif icon_type == "video":
        d.rounded_rectangle([1,1,size-1,size-1], radius=5, fill="#dc2626")
        cx,cy = size//2, size//2
        d.polygon([(cx-6,cy-8),(cx-6,cy+8),(cx+9,cy)], fill="white")
    elif icon_type == "audio":
        d.rounded_rectangle([1,1,size-1,size-1], radius=5, fill="#7c3aed")
        cx,cy = size//2,size//2+2
        d.ellipse([cx-5,cy-5,cx+5,cy+5], fill="white")
        d.line([cx,cy-5,cx,cy-11], fill="white", width=2)
        d.line([cx,cy-11,cx+6,cy-9], fill="white", width=2)
    elif icon_type == "excel":
        d.rounded_rectangle([1,1,size-1,size-1], radius=5, fill="#15803d")
        d.line([6,8,size-6,size-6], fill="white", width=3)
        d.line([size-6,8,6,size-6], fill="white", width=3)
    elif icon_type == "word":
        d.rounded_rectangle([1,1,size-1,size-1], radius=5, fill="#1d4ed8")
        cx = size//2
        d.text if False else None
        for i,x2 in enumerate([size-5,size-8,size-12]):
            d.rectangle([4,8+i*6,x2,10+i*6], fill="white")
    elif icon_type == "ppt":
        d.rounded_rectangle([1,1,size-1,size-1], radius=5, fill="#b45309")
        d.ellipse([5,5,size-5,size-5], fill="#fbbf24")
        d.rectangle([size//2,5,size-5,size//2], fill="#b45309")
    elif icon_type == "pdf":
        d.rounded_rectangle([1,1,size-1,size-1], radius=5, fill="#dc2626")
        d.text if False else None
        for i,x2 in enumerate([size-7,size-10,size-14]):
            d.rectangle([9,14+i*5,x2,16+i*5], fill="#cc1c1c")
        d.rounded_rectangle([3,3,size-3,size-3], radius=4, fill="#dc2626")
        for i in range(3):
            d.rectangle([6,10+i*6,size-6,11+i*6], fill="white")
    elif icon_type == "exe":
        import math
        d.rounded_rectangle([1,1,size-1,size-1], radius=5, fill="#374151")
        cx,cy = size//2,size//2
        R_outer,R_inner,R_hole = 13,10,4
        d.ellipse([cx-R_outer,cy-R_outer,cx+R_outer,cy+R_outer], fill="white")
        d.ellipse([cx-R_inner,cy-R_inner,cx+R_inner,cy+R_inner], fill="#374151")
        for deg in range(0,360,45):
            a = math.radians(deg)
            tx=int(cx+(R_outer-1)*math.cos(a)); ty=int(cy+(R_outer-1)*math.sin(a))
            d.ellipse([tx-3,ty-3,tx+3,ty+3], fill="white")
        d.ellipse([cx-R_inner+1,cy-R_inner+1,cx+R_inner-1,cy+R_inner-1], fill="white")
        d.ellipse([cx-R_hole,cy-R_hole,cx+R_hole,cy+R_hole], fill="#374151")
    elif icon_type == "zip":
        d.rounded_rectangle([1,1,size-1,size-1], radius=5, fill="#6b7280")
        d.rounded_rectangle([4,5,size-4,13], radius=2, fill="#d1d5db")
        d.rounded_rectangle([4,12,size-4,size-4], radius=2, fill="white")
        cx=size//2
        d.rectangle([cx-2,5,cx+2,size-4], fill="#9ca3af")
        for zy in range(7,size-5,4):
            d.rectangle([cx-4,zy,cx-2,zy+2], fill="#d1d5db")
            d.rectangle([cx+2,zy+2,cx+4,zy+4], fill="#d1d5db")
    elif icon_type == "file":
        fold=9
        d.polygon([(4,2),(size-fold-2,2),(size-3,fold+1),(size-3,size-2),(4,size-2)], fill="#f59e0b")
        d.polygon([(size-fold-2,2),(size-3,fold+1),(size-fold-2,fold+1)], fill="#b45309")
    elif icon_type == "folder":
        d.rounded_rectangle([2,8,14,14], radius=2, fill="#fbbf24")
        d.rounded_rectangle([2,12,size-2,size-3], radius=3, fill="#f59e0b")
        d.rounded_rectangle([2,12,size-2,17], radius=3, fill="#fde68a")
    elif icon_type == "code":
        d.rounded_rectangle([1,1,size-1,size-1], radius=5, fill="#6d28d9")
        cx,cy = size//2,size//2
        d.line([cx-9,cy-5,cx-14,cy], fill="white", width=2)
        d.line([cx-14,cy,cx-9,cy+5], fill="white", width=2)
        d.line([cx-2,cy+7,cx+2,cy-7], fill="#a78bfa", width=2)
        d.line([cx+9,cy-5,cx+14,cy], fill="white", width=2)
        d.line([cx+14,cy,cx+9,cy+5], fill="white", width=2)
    elif icon_type == "bash":
        d.rounded_rectangle([1,1,size-1,size-1], radius=4, fill="#0d1117")
        d.rounded_rectangle([1,1,size-1,9], radius=4, fill="#161b22")
        d.ellipse([4,3,8,7], fill="#ff5f56")
        d.ellipse([10,3,14,7], fill="#febc2e")
        d.ellipse([16,3,20,7], fill="#28c840")
        cx=6; cy=size//2+4
        d.line([cx,cy-4,cx+5,cy], fill="#4ade80", width=2)
        d.line([cx+5,cy,cx,cy+4], fill="#4ade80", width=2)
        d.rectangle([cx+8,cy+2,cx+18,cy+4], fill="#4ade80")
    elif icon_type == "html":
        cx,cy = size//2,size//2; r=size//2-2
        d.ellipse([cx-r,cy-r,cx+r,cy+r], fill="#0ea5e9")
        d.polygon([(cx-6,6),(cx+6,6),(cx+3,size-6),(cx,size-4),(cx-3,size-6)], fill="white")
    else:
        d.rounded_rectangle([2,2,size-2,size-2], radius=4, fill="#0891b2")
        d.ellipse([7,6,14,13], fill="#fef9c3")
        d.polygon([(4,size-6),(size//2,14),(size-4,size-6)], fill="#164e63")

    # Convert PIL image to QPixmap
    data = img.tobytes("raw", "RGBA")
    qimg = QImage(data, size, size, QImage.Format.Format_RGBA8888)
    return QPixmap.fromImage(qimg)


# ── Item row widget ───────────────────────────────────────────────────────────

POPUP_WIDTH = 420
ITEM_HEIGHT = 76
THUMB_SIZE  = 36
PADDING     = 10


class ItemRowWidget(QWidget):
    """One row in the clipboard popup list.
    Handles hover animation, pin/delete/move buttons, and paste on click.
    Emits signals instead of calling popup methods directly.
    """
    sig_paste   = pyqtSignal(object)   # item dict
    sig_pin     = pyqtSignal(object)
    sig_delete  = pyqtSignal(object)
    sig_move_up = pyqtSignal(object)
    sig_move_dn = pyqtSignal(object)
    sig_rclick  = pyqtSignal(object, object)  # item, QPoint

    def __init__(self, item: dict, history, profiles, colours: dict, parent=None):
        super().__init__(parent)
        self.item     = item
        self.history  = history
        self.profiles = profiles
        self.C        = colours
        self._anim_t  = 0.0
        self._anim_timer = QTimer(self)
        self._anim_timer.timeout.connect(self._anim_step)
        self._anim_target = 0.0

        # Drag state
        self._press_pos   = None
        self._is_dragging = False

        self._build()
        self.setFixedHeight(ITEM_HEIGHT)
        self.setFixedWidth(POPUP_WIDTH)

    # ── Pin state ────────────────────────────────────────────────────────────

    def _is_pinned(self) -> bool:
        if self.profiles:
            ap = self.profiles.get_active_profile()
            if ap["id"] == "general":
                return self.item.get("pinned", False)
            return self.profiles.is_pinned_in_profile(self.item["id"], ap["id"])
        return self.item.get("pinned", False)

    # ── Build ────────────────────────────────────────────────────────────────

    def _build(self):
        C    = self.C
        item = self.item
        pinned = self._is_pinned()
        self._base_bg = C["bg_pinned"] if pinned else C["bg_item"]

        main = QHBoxLayout(self)
        main.setContentsMargins(0, 0, 0, 0)
        main.setSpacing(0)

        # Left type strip
        type_col = TYPE_COLOURS.get(item.get("type",""), C["accent"])
        self._strip = QFrame(self)
        self._strip.setFixedWidth(3)
        self._strip.setStyleSheet(f"background:{type_col};border:none;")
        main.addWidget(self._strip)

        # Thumbnail
        thumb = QLabel(self)
        thumb.setFixedSize(THUMB_SIZE+8, ITEM_HEIGHT)
        thumb.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self._load_thumb(thumb, item)
        main.addWidget(thumb)
        self._thumb = thumb

        # Text area
        text_col = QVBoxLayout()
        text_col.setContentsMargins(4, 6, 4, 6)
        text_col.setSpacing(2)

        preview = self.history.get_preview(item)
        self._preview_lbl = QLabel(preview, self)
        self._preview_lbl.setWordWrap(True)
        self._preview_lbl.setMaximumWidth(240)
        self._preview_lbl.setFont(QFont("Segoe UI", 10))
        self._preview_lbl.setStyleSheet(f"color:{C['text_preview']};background:transparent;")
        text_col.addWidget(self._preview_lbl)

        src = item.get("source","Unknown")
        self._source_lbl = QLabel(f"From: {src}", self)
        self._source_lbl.setFont(QFont("Segoe UI", 8))
        self._source_lbl.setStyleSheet(f"color:{C['text_dim']};background:transparent;")
        text_col.addWidget(self._source_lbl)
        text_col.addStretch()

        main.addLayout(text_col)
        main.addStretch()

        # Action buttons grid  📌 ↑ / ✕ ↓
        btn_col = QVBoxLayout()
        btn_col.setContentsMargins(0, 6, 6, 6)
        btn_col.setSpacing(2)

        row1 = QHBoxLayout(); row1.setSpacing(2)
        row2 = QHBoxLayout(); row2.setSpacing(2)
        pin_col = C["pin"] if pinned else C["text_dim"]
        for text, sig, colour, row in [
            ("📌", self.sig_pin,     pin_col,      row1),
            ("↑",  self.sig_move_up, C["text_dim"], row1),
            ("✕",  self.sig_delete,  C["danger"],   row2),
            ("↓",  self.sig_move_dn, C["text_dim"], row2),
        ]:
            btn = _ActionButton(text, colour, C, self)
            btn.clicked_signal.connect(lambda _=None, s=sig, i=self.item: s.emit(i))
            row.addWidget(btn)

        btn_col.addLayout(row1)
        btn_col.addLayout(row2)
        main.addLayout(btn_col)

        self._apply_bg(self._base_bg)
        self.setMouseTracking(True)

    def _load_thumb(self, label: QLabel, item: dict):
        C = self.C
        itype = item.get("type","")
        if itype == "image":
            try:
                img = Image.open(item["content"])
                img.thumbnail((THUMB_SIZE, THUMB_SIZE))
                data = img.convert("RGBA").tobytes("raw","RGBA")
                qimg = QImage(data, img.width, img.height, QImage.Format.Format_RGBA8888)
                label.setPixmap(QPixmap.fromImage(qimg))
                return
            except Exception:
                pass
        # Determine icon type for files
        if itype == "file":
            files = item.get("content",[])
            if isinstance(files, list) and files:
                ext = os.path.splitext(files[0])[1].lower()
                icon_type = _FILE_TYPE_MAP.get(ext, "file")
                if len(files) > 1:
                    icon_type = "file"
                elif os.path.isdir(files[0]):
                    icon_type = "folder"
            else:
                icon_type = "file"
        else:
            icon_type = itype or "file"
        label.setPixmap(_icon_pixmap(icon_type, THUMB_SIZE))

    # ── Background ───────────────────────────────────────────────────────────

    def _apply_bg(self, hex_col: str):
        self.setStyleSheet(f"background:{hex_col};")
        # Keep labels transparent so row bg shows through
        for lbl in [self._preview_lbl, self._source_lbl, self._thumb]:
            lbl.setStyleSheet(lbl.styleSheet().split(";")[0] + ";background:transparent;")

    # ── Hover animation ──────────────────────────────────────────────────────

    def _enter_hover(self):
        self._anim_target = 1.0
        if not self._anim_timer.isActive():
            self._anim_timer.start(16)

    def _leave_hover(self):
        self._anim_target = 0.0
        if not self._anim_timer.isActive():
            self._anim_timer.start(16)

    def _anim_step(self):
        diff = self._anim_target - self._anim_t
        if abs(diff) < 0.015:
            self._anim_t = self._anim_target
            self._anim_timer.stop()
        else:
            self._anim_t += diff * 0.45
        bg = _hex_lerp(self._base_bg, self.C["bg_hover"], self._anim_t)
        self._apply_bg(bg)
        # Strip width 3→10
        w = max(3, int(3 + 7 * self._anim_t))
        self._strip.setFixedWidth(w)
        # Preview text colour
        tc = _hex_lerp(self.C["text_preview"], self.C["text"], self._anim_t)
        self._preview_lbl.setStyleSheet(f"color:{tc};background:transparent;")

    def enterEvent(self, event):
        self._enter_hover()
        super().enterEvent(event)

    def leaveEvent(self, event):
        self._leave_hover()
        super().leaveEvent(event)

    # ── Mouse events (click / drag) ─────────────────────────────────────────

    def mousePressEvent(self, event):
        if event.button() == Qt.MouseButton.LeftButton:
            self._press_pos   = event.globalPosition().toPoint()
            self._is_dragging = False
        elif event.button() == Qt.MouseButton.RightButton:
            self.sig_rclick.emit(self.item, event.globalPosition().toPoint())
        super().mousePressEvent(event)

    def mouseMoveEvent(self, event):
        if self._press_pos and event.buttons() & Qt.MouseButton.LeftButton:
            delta = event.globalPosition().toPoint() - self._press_pos
            if not self._is_dragging and (abs(delta.x()) > 6 or abs(delta.y()) > 6):
                self._is_dragging = True
        super().mouseMoveEvent(event)

    def mouseReleaseEvent(self, event):
        if event.button() == Qt.MouseButton.LeftButton:
            if not self._is_dragging:
                self.sig_paste.emit(self.item)
            self._press_pos   = None
            self._is_dragging = False
        super().mouseReleaseEvent(event)


class _ActionButton(QLabel):
    """Small clickable label used for pin/delete/move buttons.
    Blocks mouse events from propagating to the row below."""
    clicked_signal = pyqtSignal()

    def __init__(self, text: str, colour: str, C: dict, parent=None):
        super().__init__(text, parent)
        self.C      = C
        self.colour = colour
        self.setFont(QFont("Segoe UI", 10))
        self.setFixedSize(24, 24)
        self.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.setCursor(Qt.CursorShape.PointingHandCursor)
        self._idle_style  = f"color:{colour};background:{C['bg_item']};border-radius:4px;"
        self._hover_style = f"color:{colour};background:{C['bg_hover']};border-radius:4px;"
        self.setStyleSheet(self._idle_style)

    def enterEvent(self, e):
        self.setStyleSheet(self._hover_style)
        super().enterEvent(e)

    def leaveEvent(self, e):
        self.setStyleSheet(self._idle_style)
        super().leaveEvent(e)

    def mousePressEvent(self, e):
        e.accept()   # stop propagation

    def mouseReleaseEvent(self, e):
        if e.button() == Qt.MouseButton.LeftButton:
            self.clicked_signal.emit()
        e.accept()   # stop propagation


# ── Toast notification ────────────────────────────────────────────────────────

class ToastWidget(QWidget):
    def __init__(self, message: str, parent_popup=None):
        super().__init__(None, Qt.WindowType.FramelessWindowHint |
                                Qt.WindowType.WindowStaysOnTopHint |
                                Qt.WindowType.Tool)
        self.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground)
        self.setAttribute(Qt.WidgetAttribute.WA_ShowWithoutActivating)

        lbl = QLabel(message, self)
        lbl.setFont(QFont("Segoe UI", 12, QFont.Weight.Bold))
        lbl.setStyleSheet("color:#fbbf24;background:#1c1c1c;border-radius:6px;padding:10px 20px;")

        lay = QHBoxLayout(self)
        lay.setContentsMargins(0,0,0,0)
        lay.addWidget(lbl)
        self.adjustSize()

        # Position above the popup or above cursor
        if parent_popup and parent_popup.isVisible():
            px = parent_popup.x() + parent_popup.width()//2 - self.width()//2
            py = parent_popup.y() - self.height() - 8
        else:
            cx,cy = pyautogui.position()
            px,py = cx - self.width()//2, cy - self.height() - 16
        self.move(max(0,px), max(0,py))
        self.setWindowOpacity(0.70)
        self.show()

        self._alpha = 0.70
        self._fade_timer = QTimer(self)
        self._fade_timer.timeout.connect(self._fade_step)
        QTimer.singleShot(2000, self._start_fade)

    def _start_fade(self):
        self._fade_timer.start(40)

    def _fade_step(self):
        self._alpha -= 0.07
        if self._alpha <= 0:
            self._fade_timer.stop()
            self.close()
            self.deleteLater()
        else:
            self.setWindowOpacity(self._alpha)


# ── Side panel (multi-file list) ──────────────────────────────────────────────

class SidePanelWidget(QWidget):
    """Floating panel to the right of the popup listing files in a multi-file item."""

    PANEL_W   = 280
    ROW_H     = 32

    def __init__(self, files: list, item: dict, history, colours: dict,
                 on_paste_file, parent_popup, parent=None):
        super().__init__(None, Qt.WindowType.FramelessWindowHint |
                                Qt.WindowType.WindowStaysOnTopHint |
                                Qt.WindowType.Tool)
        self.setAttribute(Qt.WidgetAttribute.WA_ShowWithoutActivating)
        _set_no_activate(int(self.winId()))

        self.files    = files
        self.item     = item
        self.history  = history
        self.C        = colours
        self.on_paste_file = on_paste_file
        self._parent_popup = parent_popup
        self._close_timer  = QTimer(self)
        self._close_timer.setSingleShot(True)
        self._close_timer.timeout.connect(self.close)

        self.setStyleSheet(f"background:{colours['bg']};border:1px solid {colours['border']};")
        lay = QVBoxLayout(self)
        lay.setContentsMargins(0,0,0,0)
        lay.setSpacing(0)

        # Header
        hdr = QLabel(f"  {len(files)} files", self)
        hdr.setFont(QFont("Segoe UI", 9, QFont.Weight.Bold))
        hdr.setFixedHeight(28)
        hdr.setStyleSheet(f"background:{colours['accent']};color:white;padding-left:6px;")
        lay.addWidget(hdr)

        # Scrollable list
        self._list = QListWidget(self)
        self._list.setStyleSheet(f"""
            QListWidget {{ background:{colours['bg']}; border:none; outline:none; }}
            QListWidget::item {{ height:{self.ROW_H}px; color:{colours['text']}; padding-left:6px; }}
            QListWidget::item:hover {{ background:{colours['bg_hover']}; }}
            QListWidget::item:selected {{ background:{colours['bg_hover']}; }}
        """)
        self._list.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        self._list.setFixedWidth(self.PANEL_W)
        max_visible = min(len(files), 12)
        self._list.setFixedHeight(max_visible * self.ROW_H)
        self._list.itemClicked.connect(self._on_file_click)

        for fp in files:
            basename = os.path.basename(fp)
            ext      = os.path.splitext(fp)[1].lower()
            itype    = _FILE_TYPE_MAP.get(ext, "folder" if os.path.isdir(fp) else "file")
            qi       = QListWidgetItem(f"  {basename}")
            qi.setData(Qt.ItemDataRole.UserRole, fp)
            qi.setIcon(QIcon(_icon_pixmap(itype, 20)))
            self._list.addItem(qi)

        lay.addWidget(self._list)
        self.adjustSize()

        # Mouse-leave timer management
        self._list.setMouseTracking(True)
        self.setMouseTracking(True)

    def _on_file_click(self, item: QListWidgetItem):
        fp = item.data(Qt.ItemDataRole.UserRole)
        self.close()
        self.on_paste_file(fp)

    def arm_close_timer(self):
        self._close_timer.start(250)

    def cancel_close_timer(self):
        self._close_timer.stop()

    def enterEvent(self, e):
        self.cancel_close_timer()
        super().enterEvent(e)

    def leaveEvent(self, e):
        self.arm_close_timer()
        super().leaveEvent(e)


# ── Main popup window ─────────────────────────────────────────────────────────

class _PopupSignals(QObject):
    """Signals for thread-safe cross-thread calls into DropdownPopup.
    Emitting a signal from any thread safely invokes the connected slot
    on the thread that owns the QObject (the Qt main thread).
    """
    show_sig = pyqtSignal(int, int)   # x, y
    hide_sig = pyqtSignal()


class DropdownPopup(QObject):
    """
    The main ClipDrop popup window.

    Interface (same as tkinter version so main.py needs minimal changes):
        show(x, y)   — show the popup at screen position (x, y)
        hide()       — hide / destroy the popup

    Thread safety: show() and hide() are called from background threads
    (mouse hook, hotkey handler, signal file watcher). They emit Qt signals
    which are automatically queued to the main thread's event loop.
    """

    def __init__(self, root=None, history_manager=None, watcher=None, profile_manager=None):
        super().__init__()
        # root is unused in Qt but kept for API compatibility
        self.history  = history_manager
        self.watcher  = watcher
        self.profiles = profile_manager

        self._popup       = None   # The QWidget window
        self._side_panel  = None   # SidePanelWidget if open
        self._paste_target = None  # hwnd of window that was focused at right-click
        self._colours     = DARK   # Current theme dict

        # Thread-safe signals — connected to slots that run on this object's thread
        self._sig = _PopupSignals()
        self._sig.show_sig.connect(self._build_and_show)
        self._sig.hide_sig.connect(self._do_hide)

    # ── Public API ───────────────────────────────────────────────────────────

    def show(self, x: int, y: int):
        """Show popup at (x, y). Fully thread-safe — emits a queued signal."""
        if not self._paste_target:
            try:
                self._paste_target = win32gui.GetForegroundWindow()
            except Exception:
                pass
        self._sig.show_sig.emit(x, y)

    def hide(self):
        """Hide and destroy the popup. Fully thread-safe — emits a queued signal."""
        self._sig.hide_sig.emit()

    # ── Build ─────────────────────────────────────────────────────────────────

    def _build_and_show(self, x: int, y: int):
        self._do_hide()

        # Theme + opacity from settings
        theme = self.history.settings.get("theme", "dark") if self.history else "dark"
        self._colours = DARK if theme == "dark" else LIGHT
        self._opacity = self.history.settings.get("transparency", 1.0) if self.history else 1.0
        C = self._colours

        # Get items
        if self.profiles:
            items = self.profiles.get_active_items()
        else:
            items = self.history.get_all() if self.history else []

        # Build window
        popup = QWidget(None, Qt.WindowType.FramelessWindowHint |
                               Qt.WindowType.WindowStaysOnTopHint |
                               Qt.WindowType.Tool)
        popup.setAttribute(Qt.WidgetAttribute.WA_ShowWithoutActivating)
        popup.setAttribute(Qt.WidgetAttribute.WA_DeleteOnClose)
        popup.setStyleSheet(f"background:{C['bg']};border:1px solid {C['border']};")
        popup.setWindowOpacity(self._opacity)
        self._popup = popup

        # WS_EX_NOACTIVATE — show window, then apply (winId valid only after show)
        popup.show()
        QTimer.singleShot(0, lambda: _set_no_activate(int(popup.winId())))

        main_lay = QVBoxLayout(popup)
        main_lay.setContentsMargins(1,1,1,1)
        main_lay.setSpacing(0)

        # ── Header ────────────────────────────────────────────────────────────
        self._count_lbl = None
        header = self._build_header(popup, items, C)
        main_lay.addWidget(header)

        # ── Separator ─────────────────────────────────────────────────────────
        sep = QFrame(popup); sep.setFrameShape(QFrame.Shape.HLine)
        sep.setStyleSheet(f"color:{C['border']};")
        main_lay.addWidget(sep)

        # ── Search bar ────────────────────────────────────────────────────────
        search_bar, self._search_edit = self._build_search(popup, C)
        main_lay.addWidget(search_bar)

        sep2 = QFrame(popup); sep2.setFrameShape(QFrame.Shape.HLine)
        sep2.setStyleSheet(f"color:{C['border']};")
        main_lay.addWidget(sep2)

        # ── Item list ────────────────────────────────────────────────────────
        self._items_all    = items
        self._list_container = QWidget(popup)
        self._list_lay     = QVBoxLayout(self._list_container)
        self._list_lay.setContentsMargins(0,0,0,0)
        self._list_lay.setSpacing(0)

        if items:
            self._populate_list(items)
        else:
            self._build_empty_label(self._list_container, C)

        scroll = QScrollArea(popup)
        scroll.setWidget(self._list_container)
        scroll.setWidgetResizable(True)
        scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        scroll.setStyleSheet(f"QScrollArea{{border:none;background:{C['bg']};}} "
                             f"QScrollBar:vertical{{width:8px;background:{C['bg_item']};}} "
                             f"QScrollBar::handle:vertical{{background:{C['border']};border-radius:4px;}}")
        scroll.setFixedWidth(POPUP_WIDTH + 10)
        max_h = min(len(items) * ITEM_HEIGHT + 4, 480) if items else 100
        scroll.setFixedHeight(max_h)
        main_lay.addWidget(scroll)

        # Connect search
        self._search_edit.textChanged.connect(self._on_search)

        # Escape to close
        from PyQt6.QtGui import QKeySequence, QShortcut
        sc = QShortcut(QKeySequence("Escape"), popup)
        sc.activated.connect(self.hide)

        popup.adjustSize()
        self._position_popup(x, y)
        popup.raise_()

    def _build_header(self, parent, items, C) -> QWidget:
        hdr = QWidget(parent)
        hdr.setFixedHeight(36)
        hdr.setStyleSheet(f"background:{C['accent']};")

        lay = QHBoxLayout(hdr)
        lay.setContentsMargins(PADDING, 0, PADDING, 0)
        lay.setSpacing(6)

        # Title — also drag handle
        title = QLabel("📋  ClipDrop", hdr)
        title.setFont(QFont("Segoe UI", 10, QFont.Weight.Bold))
        title.setStyleSheet("color:white;background:transparent;")
        lay.addWidget(title)

        lay.addStretch()

        # Profile switcher
        if self.profiles:
            active_name = self.profiles.get_active_profile()["name"]
            prof_btn = QLabel(f"{active_name}  ▾", hdr)
            prof_btn.setFont(QFont("Segoe UI", 8, QFont.Weight.Bold))
            prof_btn.setStyleSheet("color:#c7d2fe;background:transparent;")
            prof_btn.setCursor(Qt.CursorShape.PointingHandCursor)
            prof_btn.mousePressEvent = lambda e, b=prof_btn: self._show_profile_menu(b)
            lay.addWidget(prof_btn)
            self._prof_btn = prof_btn

        # Item count
        count_lbl = QLabel(f"{len(items)} items", hdr)
        count_lbl.setFont(QFont("Segoe UI", 8))
        count_lbl.setStyleSheet("color:#c7d2fe;background:transparent;")
        lay.addWidget(count_lbl)
        self._count_lbl = count_lbl

        # Make header draggable
        self._drag_pos = None
        def _hdr_press(e):
            if e.button() == Qt.MouseButton.LeftButton:
                self._drag_pos = e.globalPosition().toPoint() - self._popup.pos()
        def _hdr_move(e):
            if self._drag_pos and e.buttons() & Qt.MouseButton.LeftButton:
                self._popup.move(e.globalPosition().toPoint() - self._drag_pos)
        def _hdr_release(e):
            self._drag_pos = None
        hdr.mousePressEvent   = _hdr_press
        hdr.mouseMoveEvent    = _hdr_move
        hdr.mouseReleaseEvent = _hdr_release

        return hdr

    def _build_search(self, parent, C) -> tuple:
        bar = QWidget(parent)
        bar.setStyleSheet(f"background:{C['bg_item']};")
        lay = QHBoxLayout(bar)
        lay.setContentsMargins(8, 4, 8, 4)
        lay.setSpacing(4)

        icon = QLabel("🔍", bar)
        icon.setFont(QFont("Segoe UI", 9))
        icon.setStyleSheet(f"color:{C['text_dim']};background:transparent;")
        lay.addWidget(icon)

        edit = QLineEdit(bar)
        edit.setPlaceholderText("Search clipboard…")
        edit.setStyleSheet(f"""
            QLineEdit {{
                background:transparent; color:{C['text']};
                border:none; font-family:'Segoe UI'; font-size:10pt;
            }}
        """)
        lay.addWidget(edit)

        clear = QLabel("✕", bar)
        clear.setFont(QFont("Segoe UI", 9))
        clear.setStyleSheet(f"color:{C['text_dim']};background:transparent;")
        clear.setCursor(Qt.CursorShape.PointingHandCursor)
        clear.mousePressEvent = lambda e: edit.clear()
        lay.addWidget(clear)

        return bar, edit

    def _build_empty_label(self, parent, C):
        lbl = QLabel("No clipboard history yet.\nCopy something to get started!", parent)
        lbl.setAlignment(Qt.AlignmentFlag.AlignCenter)
        lbl.setFont(QFont("Segoe UI", 10))
        lbl.setStyleSheet(f"color:{C['text_dim']};background:{C['bg']};padding:24px;")
        self._list_lay.addWidget(lbl)

    def _populate_list(self, items: list):
        C = self._colours
        # Clear existing rows
        while self._list_lay.count():
            child = self._list_lay.takeAt(0)
            if child.widget():
                child.widget().deleteLater()

        for item in items:
            row = ItemRowWidget(item, self.history, self.profiles, C, self._list_container)
            row.sig_paste.connect(self._paste_item)
            row.sig_pin.connect(self._toggle_pin)
            row.sig_delete.connect(self._delete_item)
            row.sig_move_up.connect(self._move_up)
            row.sig_move_dn.connect(self._move_down)
            row.sig_rclick.connect(self._show_send_to_menu)

            # Multi-file side panel on hover
            files = item.get("content", [])
            is_multi = (item.get("type") == "file" and isinstance(files, list) and len(files) > 1)
            is_folder = (item.get("type") == "file" and isinstance(files, list) and
                         len(files) == 1 and os.path.isdir(files[0]))
            if is_multi or is_folder:
                if is_folder:
                    try:
                        panel_files = sorted(
                            [os.path.join(files[0], n) for n in os.listdir(files[0])],
                            key=lambda p: (not os.path.isdir(p), os.path.basename(p).lower()))
                    except Exception:
                        panel_files = files
                else:
                    panel_files = files
                row.enterEvent = self._make_panel_enter(row, item, panel_files, row.enterEvent)
                row.leaveEvent = self._make_panel_leave(row, row.leaveEvent)

            sep = QFrame(self._list_container)
            sep.setFrameShape(QFrame.Shape.HLine)
            sep.setStyleSheet(f"color:{C['border']};")
            self._list_lay.addWidget(row)
            self._list_lay.addWidget(sep)

        self._list_lay.addStretch()

    # ── Side panel helpers ────────────────────────────────────────────────────

    def _make_panel_enter(self, row, item, panel_files, original_enter):
        def enter(e):
            original_enter(e)
            self._open_side_panel(row, item, panel_files)
        return enter

    def _make_panel_leave(self, row, original_leave):
        def leave(e):
            original_leave(e)
            if self._side_panel:
                self._side_panel.arm_close_timer()
        return leave

    def _open_side_panel(self, row: QWidget, item: dict, files: list):
        if self._side_panel:
            try:
                self._side_panel.cancel_close_timer()
                self._side_panel.close()
            except Exception:
                pass
            self._side_panel = None

        def paste_single_file(fp):
            file_item = {
                "id":      hashlib.md5(fp.encode()).hexdigest(),
                "type":    "file",
                "content": [fp],
                "source":  os.path.dirname(fp),
            }
            self._do_paste(file_item)

        panel = SidePanelWidget(files, item, self.history, self._colours,
                                paste_single_file, self._popup)
        self._side_panel = panel

        # Position to the right of popup
        if self._popup:
            px = self._popup.x() + self._popup.width()
            py = self._popup.y() + row.y()
            panel.move(px, py)
        panel.show()

    # ── Position ──────────────────────────────────────────────────────────────

    def _position_popup(self, x: int, y: int):
        popup = self._popup
        popup.adjustSize()
        w = popup.width()
        h = popup.height()
        screen = QApplication.primaryScreen().geometry()
        sw, sh = screen.width(), screen.height()
        px = x if x + w <= sw else sw - w - 4
        px = max(0, px)
        py = y if y + h <= sh else y - h
        py = max(0, py)
        popup.move(px, py)

    # ── Search ────────────────────────────────────────────────────────────────

    def _on_search(self, query: str):
        q = query.strip().lower()
        if not q:
            filtered = self._items_all
        else:
            filtered = [
                i for i in self._items_all
                if q in self.history.get_preview(i).lower()
                or q in i.get("source","").lower()
                or q in i.get("type","").lower()
            ]
        self._populate_list(filtered)
        if self._count_lbl:
            if len(filtered) < len(self._items_all):
                self._count_lbl.setText(f"{len(filtered)} / {len(self._items_all)} items")
            else:
                self._count_lbl.setText(f"{len(self._items_all)} items")

    # ── Profile menu ──────────────────────────────────────────────────────────

    def _show_profile_menu(self, btn: QLabel):
        if not self.profiles:
            return
        menu = QMenu()
        menu.setStyleSheet(f"""
            QMenu {{ background:{self._colours['bg_item']}; color:{self._colours['text']};
                     border:1px solid {self._colours['border']}; font-family:'Segoe UI'; }}
            QMenu::item:selected {{ background:{self._colours['bg_hover']}; }}
        """)
        active_id = self.profiles.get_active_profile()["id"]
        for prof in self.profiles.get_all_profiles():
            name = ("✓ " if prof["id"] == active_id else "   ") + prof["name"]
            act  = menu.addAction(name)
            act.setData(prof["id"])
        chosen = menu.exec(btn.mapToGlobal(QPoint(0, btn.height())))
        if chosen:
            self.profiles.set_active(chosen.data())
            self._refresh()

    def _show_send_to_menu(self, item: dict, gpos: QPoint):
        if not self.profiles:
            return
        menu = QMenu()
        menu.setStyleSheet(f"""
            QMenu {{ background:{self._colours['bg_item']}; color:{self._colours['text']};
                     border:1px solid {self._colours['border']}; font-family:'Segoe UI'; }}
            QMenu::item:selected {{ background:{self._colours['bg_hover']}; }}
        """)
        menu.addAction("Send to profile…").setEnabled(False)
        menu.addSeparator()
        for prof in self.profiles.get_all_profiles():
            if prof.get("built_in"):
                continue
            act = menu.addAction(prof["name"])
            act.setData(prof["id"])
        chosen = menu.exec(gpos)
        if chosen and chosen.data():
            self.profiles.add_item_to_profile(item["id"], chosen.data())
            self._show_toast(f'Sent to "{chosen.text()}"')

    # ── Actions ───────────────────────────────────────────────────────────────

    def _toggle_pin(self, item: dict):
        if self.profiles:
            active = self.profiles.get_active_profile()
            if active["id"] == "general":
                self.history.toggle_pin(item["id"])
            else:
                self.profiles.toggle_pin_in_profile(item["id"], active["id"])
        else:
            self.history.toggle_pin(item["id"])
        self._refresh()

    def _delete_item(self, item: dict):
        if self.profiles:
            active = self.profiles.get_active_profile()
            if active["id"] == "general":
                in_named = any(
                    item["id"] in p.get("item_ids", [])
                    for p in self.profiles.get_all_profiles()
                    if not p.get("built_in")
                )
                if in_named:
                    for it in self.history.items:
                        if it["id"] == item["id"]:
                            it["hidden"] = True
                            self.history._save_history()
                            break
                else:
                    self.profiles.remove_item_from_all(item["id"])
                    self.history.delete_item(item["id"])
            else:
                self.profiles.remove_item_from_profile(item["id"], active["id"])
        else:
            self.history.delete_item(item["id"])
        self._refresh()

    def _move_up(self, item: dict):
        self.history.move_up(item["id"])
        self._refresh()

    def _move_down(self, item: dict):
        self.history.move_down(item["id"])
        self._refresh()

    def _refresh(self):
        """Rebuild popup in-place at current position. No flicker."""
        if self._popup:
            x = self._popup.x()
            y = self._popup.y()
            self._build_and_show(x, y)

    # ── Hide ──────────────────────────────────────────────────────────────────

    def _do_hide(self):
        if self._side_panel:
            try:
                self._side_panel.close()
            except Exception:
                pass
            self._side_panel = None
        if self._popup:
            try:
                self._popup.close()
            except Exception:
                pass
            self._popup = None

    # ── Paste ─────────────────────────────────────────────────────────────────

    def _paste_item(self, item: dict):
        self.hide()
        QTimer.singleShot(250, lambda: self._do_paste(item))

    def _do_paste(self, item: dict):
        if self.watcher:
            self.watcher.paused = True
        try:
            win32clipboard.OpenClipboard()
            win32clipboard.EmptyClipboard()
            if item["type"] in ("text", "url", "code", "bash"):
                win32clipboard.SetClipboardData(win32con.CF_UNICODETEXT, item["content"])
                if self.watcher:
                    self.watcher.last_seen = hashlib.md5(
                        item["content"].encode("utf-8", errors="ignore")).hexdigest()
            elif item["type"] == "file":
                files = item["content"]
                if isinstance(files, list):
                    file_block = b""
                    for f in files:
                        file_block += f.encode("utf-16-le") + b"\x00\x00"
                    file_block += b"\x00\x00"
                    header = struct.pack("<5I", 20, 0, 0, 0, 1)
                    win32clipboard.SetClipboardData(win32con.CF_HDROP, header + file_block)
                    if self.watcher:
                        self.watcher.last_seen = hashlib.md5(
                            str(files).encode("utf-8", errors="ignore")).hexdigest()
            elif item["type"] == "image":
                img = Image.open(item["content"])
                output = io.BytesIO()
                img.convert("RGB").save(output, "BMP")
                data = output.getvalue()[14:]
                output.close()
                win32clipboard.SetClipboardData(win32con.CF_DIB, data)
            win32clipboard.CloseClipboard()
        except Exception as e:
            print(f"[ClipDrop] Paste error: {e}")
            try:
                win32clipboard.CloseClipboard()
            except Exception:
                pass
            if self.watcher:
                self.watcher.paused = False
            return

        # Restore focus for desktop paste
        _target = getattr(self, "_paste_target", None)
        self._paste_target = None
        if _target:
            try:
                _cls = win32gui.GetClassName(_target)
                if _cls in ("Progman", "WorkerW"):
                    _sv = win32gui.FindWindowEx(_target, None, "SHELLDLL_DefView", None)
                    if _sv:
                        _lv = win32gui.FindWindowEx(_sv, None, "SysListView32", None)
                        if _lv:
                            _target = _lv
                    win32gui.SetForegroundWindow(_target)
                    win32gui.BringWindowToTop(_target)
                    time.sleep(0.1)
            except Exception:
                pass

        pyautogui.hotkey("ctrl", "v")

        if self.watcher:
            time.sleep(0.5)
            try:
                if item["type"] in ("text", "url", "code", "bash"):
                    self.watcher.last_seen = hashlib.md5(
                        item["content"].encode("utf-8")).hexdigest()
                elif item["type"] == "file":
                    self.watcher.last_seen = hashlib.md5(
                        str(item["content"]).encode("utf-8")).hexdigest()
            except Exception:
                pass
            self.watcher.paused = False

    # ── Toast ──────────────────────────────────────────────────────────────────

    def _show_toast(self, message: str):
        toast = ToastWidget(message, self._popup)
        # Keep reference so it isn't GC'd
        if not hasattr(self, "_toasts"):
            self._toasts = []
        self._toasts.append(toast)
        toast.destroyed.connect(lambda: self._toasts.remove(toast) if toast in self._toasts else None)
