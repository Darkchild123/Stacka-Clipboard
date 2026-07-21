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
import keyboard

from PIL import Image

from PyQt6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel, QLineEdit,
    QListWidget, QListWidgetItem, QScrollArea, QFrame,
    QAbstractItemView, QMenu, QApplication, QSizePolicy,
    QGraphicsOpacityEffect, QGraphicsDropShadowEffect, QStyledItemDelegate,
)
from PyQt6.QtCore import (
    Qt, QTimer, QPoint, QSize, QRect, QRectF, QPointF, QPropertyAnimation,
    QVariantAnimation, QEasingCurve, pyqtSignal, QObject, pyqtSlot,
    QThread, QEvent, QUrl, QMimeData, QByteArray,
)
from PyQt6.QtGui import (
    QColor, QPainter, QPen, QBrush, QFont, QFontMetrics,
    QPixmap, QImage, QCursor, QIcon, QPalette, QPolygonF, QDrag,
)
from PyQt6.QtSvg import QSvgRenderer

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
    "hex":    "#ec4899",
    "file":   "#f59e0b",
    "folder": "#f59e0b",
    "code":   "#7c3aed",
    "python": "#4B8BBE",
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
for _e in ['.docx','.doc','.odt','.pages']:
    _FILE_TYPE_MAP[_e] = "word"
for _e in ['.pptx','.ppt','.odp','.key']:
    _FILE_TYPE_MAP[_e] = "ppt"
for _e in ['.pdf']:
    _FILE_TYPE_MAP[_e] = "pdf"
for _e in ['.exe','.msi','.apk','.dmg','.deb','.rpm','.jar']:
    _FILE_TYPE_MAP[_e] = "exe"
for _e in ['.dll','.sys','.ocx','.drv']:
    _FILE_TYPE_MAP[_e] = "dll"
for _e in ['.zip','.rar','.7z','.tar','.gz','.bz2','.xz','.cab','.iso']:
    _FILE_TYPE_MAP[_e] = "zip"
for _e in ['.html','.htm','.xhtml','.php','.asp','.aspx','.jsp']:
    _FILE_TYPE_MAP[_e] = "html"
for _e in ['.py','.pyw','.pyi']:
    _FILE_TYPE_MAP[_e] = "python"
for _e in ['.js','.ts','.jsx','.tsx','.java','.c','.cpp','.h','.cs',
           '.go','.rs','.rb','.swift','.kt','.r','.sql','.css','.scss',
           '.vue','.svelte','.lua','.bat','.cmd','.sh','.bash','.ps1']:
    _FILE_TYPE_MAP[_e] = "code"
# NOTE: "txt" (a text FILE — paper with stripes) is deliberately a
# DIFFERENT icon from "text" (clipboard CHARACTERS — font symbol).
# One is a file on disk, the other is a character run. Never merge them.
for _e in ['.txt','.rtf','.md','.log','.ini','.cfg','.conf','.json','.xml','.yaml','.yml','.toml']:
    _FILE_TYPE_MAP[_e] = "txt"


# ── Helpers ──────────────────────────────────────────────────────────────────

def _qc(hex_str: str) -> QColor:
    return QColor(hex_str)

def _hex_lerp(c1: str, c2: str, t: float) -> str:
    t = max(0.0, min(1.0, t))
    r1,g1,b1 = int(c1[1:3],16), int(c1[3:5],16), int(c1[5:7],16)
    r2,g2,b2 = int(c2[1:3],16), int(c2[3:5],16), int(c2[5:7],16)
    return "#{:02x}{:02x}{:02x}".format(
        int(r1+(r2-r1)*t), int(g1+(g2-g1)*t), int(b1+(b2-b1)*t))

def _shade(col: str, t: float) -> str:
    """Lighten (t>0, toward white) or darken (t<0, toward black) a hex colour."""
    return _hex_lerp(col, "#ffffff" if t >= 0 else "#000000", abs(t))

def _grad_v(top: str, bottom: str) -> str:
    """QSS vertical linear gradient — the '3D surface' fill."""
    return (f"qlineargradient(x1:0,y1:0,x2:0,y2:1,"
            f"stop:0 {top},stop:1 {bottom})")

def _scrollbar_qss(C: dict) -> str:
    """Shared modern scrollbar: transparent track, rounded gradient handle
    in ACCENT colour so it's visible even while inactive, brighter on
    hover, lightest while dragging. No arrow buttons."""
    handle_top = _shade(C["accent"], 0.12)
    handle_bot = _shade(C["accent"], -0.22)
    hover      = _shade(C["accent"], 0.32)
    return (
        f"QScrollBar:vertical {{background:transparent;width:13px;"
        f"margin:2px 2px 2px 0;border:none;}}"
        f"QScrollBar::handle:vertical {{"
        f"background:qlineargradient(x1:0,y1:0,x2:1,y2:0,"
        f"stop:0 {handle_top},stop:1 {handle_bot});"
        f"border-radius:5px;min-height:28px;}}"
        f"QScrollBar::handle:vertical:hover {{background:{hover};}}"
        f"QScrollBar::handle:vertical:pressed {{background:{C['accent_light']};}}"
        f"QScrollBar::add-line:vertical,QScrollBar::sub-line:vertical {{height:0;}}"
        f"QScrollBar::add-page:vertical,QScrollBar::sub-page:vertical "
        f"{{background:none;}}")

def _activate_for_menu(widget):
    """Make a window able to host a well-behaved QMenu.

    Menus opened from a WS_EX_NOACTIVATE window can't establish their
    mouse grab reliably: they don't dismiss on outside clicks and can
    survive as stuck orphans on screen. Strip the flag and foreground
    the owner just before menu.exec(); the paste worker re-foregrounds
    the real paste target before any Ctrl+V, so pasting is unaffected.
    """
    try:
        win = widget.window()
        hwnd = int(win.winId())
        ex = win32gui.GetWindowLong(hwnd, win32con.GWL_EXSTYLE)
        if ex & win32con.WS_EX_NOACTIVATE:
            win32gui.SetWindowLong(hwnd, win32con.GWL_EXSTYLE,
                                   ex & ~win32con.WS_EX_NOACTIVATE)
        win32gui.SetForegroundWindow(hwnd)
        win.activateWindow()
    except Exception:
        pass


def _set_no_activate(hwnd: int):
    """Apply WS_EX_NOACTIVATE so the window never steals keyboard focus."""
    try:
        ex = win32gui.GetWindowLong(hwnd, win32con.GWL_EXSTYLE)
        win32gui.SetWindowLong(hwnd, win32con.GWL_EXSTYLE,
                               ex | win32con.WS_EX_NOACTIVATE)
    except Exception:
        pass

_ICON_CACHE: dict = {}   # (icon_type, size, colour_hint) → QPixmap; PIL redraw
                         # is ~0.5 ms each — noticeable when a 247-file panel
                         # rebuilds.

_SS = 4   # supersampling factor: icons raster at 4× then LANCZOS-downscale
          # — the difference between jagged and crisp edges at 16–36 px.


class _ScaledDraw:
    """Proxy around PIL ImageDraw that multiplies every coordinate (and
    width/radius/font size) by a factor. Icon branches keep their logical
    16/20/36-px coordinates; the actual raster happens supersampled."""

    def __init__(self, draw, s):
        self._d = draw
        self._s = s

    def _xy(self, xy):
        s = self._s
        return [tuple(v * s for v in p) if isinstance(p, (tuple, list))
                else p * s
                for p in xy]

    def _kw(self, kw):
        if isinstance(kw.get("width"), (int, float)):
            kw["width"] = max(1, round(kw["width"] * self._s))
        if isinstance(kw.get("radius"), (int, float)):
            kw["radius"] = kw["radius"] * self._s
        return kw

    def rectangle(self, xy, **kw):         self._d.rectangle(self._xy(xy), **self._kw(kw))
    def rounded_rectangle(self, xy, **kw): self._d.rounded_rectangle(self._xy(xy), **self._kw(kw))
    def ellipse(self, xy, **kw):           self._d.ellipse(self._xy(xy), **self._kw(kw))
    def line(self, xy, **kw):              self._d.line(self._xy(xy), **self._kw(kw))
    def polygon(self, xy, **kw):           self._d.polygon(self._xy(xy), **self._kw(kw))

    def text(self, xy, s, font=None, **kw):
        if font is not None and getattr(font, "size", None):
            font = _bold_font(int(font.size * self._s)) or font
        self._d.text(tuple(v * self._s for v in xy), s, font=font, **kw)


# Types drawn as a coloured tile + a letter (Qt SVG can't render <text>, and
# PIL loads the bold TTF directly so letters stay crisp). Everything else is
# a pure vector icon rendered from ICON_SVGS via Qt's SVG engine.
_LETTER_TYPES = {"text", "word", "excel", "ppt", "pdf", "hex"}

# Icon packs (Settings -> Icon pack). "default" is the built-in set below;
# "labeled" is the per-extension document pack in icon_packs.py. These three
# TYPES always use the Default icons regardless of pack (user preference).
_ACTIVE_PACK  = "default"
_PINNED_TYPES = {"python", "bash", "text"}


def set_icon_pack(name: str):
    """Switch the active icon pack ('default' | 'labeled'). Cheap — the
    icon cache is keyed by pack, so both packs coexist cached."""
    global _ACTIVE_PACK
    _ACTIVE_PACK = name or "default"


def _icon_pixmap(icon_type: str, size: int = 32, colour_hint: str = None,
                 ext: str = None) -> QPixmap:
    """Crash-proof, cached icon factory.

    Vector shapes render from SVG (crisp at any size, smooth curves and
    gradients PIL can't do); letter tiles and the hex swatch are drawn
    with PIL. An unhandled exception in a slot aborts the whole app, so
    any drawing error falls back to a plain colour badge.

    colour_hint: for "hex" icons — the actual colour code the swatch shows.
    ext: file extension — lets the Labeled pack pick a per-extension icon.
    """
    key = (_ACTIVE_PACK, icon_type, size, colour_hint, ext)
    if key in _ICON_CACHE:
        return _ICON_CACHE[key]
    try:
        pm = None
        # Labeled pack: per-extension document icons, EXCEPT the pinned
        # types which always use the Default (my) icons.
        if (_ACTIVE_PACK == "labeled" and ext
                and icon_type not in _PINNED_TYPES):
            import icon_packs
            pm = icon_packs.labeled_pixmap(ext, size)
        if pm is None:                       # Default pack (or pack miss)
            if icon_type in _LETTER_TYPES:
                pm = _draw_letter_tile(icon_type, size, colour_hint)
            else:
                svg = ICON_SVGS.get(icon_type) or ICON_SVGS["default"]
                pm = _svg_pixmap(svg, size)
        _ICON_CACHE[key] = pm
        return pm
    except Exception as e:
        print(f"[ClipDrop] Icon draw failed for '{icon_type}' @ {size}px: {e}")
        from PIL import ImageDraw
        img = Image.new("RGBA", (size, size), (0, 0, 0, 0))
        d = ImageDraw.Draw(img)
        d.rounded_rectangle([1, 1, size-1, size-1], radius=4, fill="#64748b")
        data = img.tobytes("raw", "RGBA")
        qimg = QImage(data, size, size, QImage.Format.Format_RGBA8888)
        return QPixmap.fromImage(qimg)


def _svg_pixmap(svg: str, size: int) -> QPixmap:
    """Render an SVG string to a QPixmap at `size` px, antialiased."""
    r = QSvgRenderer(QByteArray(svg.encode("utf-8")))
    img = QImage(size, size, QImage.Format.Format_ARGB32)
    img.fill(Qt.GlobalColor.transparent)
    p = QPainter(img)
    p.setRenderHint(QPainter.RenderHint.Antialiasing)
    r.render(p)
    p.end()
    return QPixmap.fromImage(img)


_FONT_CACHE: dict = {}   # px → PIL font (or None if no TTF could be loaded)


def _bold_font(px: int):
    """Bold TTF for letter icons (Office tiles, PDF). None if unavailable —
    callers must draw a shape fallback so the icon never goes blank."""
    if px in _FONT_CACHE:
        return _FONT_CACHE[px]
    from PIL import ImageFont
    font = None
    for name in ("arialbd.ttf", "segoeuib.ttf", "seguisb.ttf", "arial.ttf"):
        try:
            font = ImageFont.truetype(name, px)
            break
        except Exception:
            continue
    _FONT_CACHE[px] = font
    return font


def _gear_svg(cx, cy, r_out, r_in, r_hole, tw, th, fill, hole):
    teeth = "".join(
        f'<rect x="{cx-tw/2}" y="{cy-r_out}" width="{tw}" height="{th}" '
        f'rx="2" fill="{fill}" transform="rotate({d} {cx} {cy})"/>'
        for d in range(0, 360, 45))
    return (f'{teeth}<circle cx="{cx}" cy="{cy}" r="{r_in}" fill="{fill}"/>'
            f'<circle cx="{cx}" cy="{cy}" r="{r_hole}" fill="{hole}"/>')


_TILE = '<rect x="8" y="8" width="112" height="112" rx="24" fill="{c}"/>'

# Vector file-type icons, authored as SVG and rendered by Qt (QSvgRenderer).
# Curves and gradients here are things PIL primitives can't draw cleanly —
# this is why the icons are crisp at every size. Letter tiles (Office/PDF)
# and the dynamic hex swatch are drawn separately in _draw_letter_tile.
ICON_SVGS = {
 "python": '<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 128 128">'
   '<defs><linearGradient id="pb" x1="0" y1="0" x2="1" y2="1"><stop offset="0" stop-color="#5A9FD4"/><stop offset="1" stop-color="#306998"/></linearGradient>'
   '<linearGradient id="py" x1="0" y1="0" x2="1" y2="1"><stop offset="0" stop-color="#FFE873"/><stop offset="1" stop-color="#FFD43B"/></linearGradient></defs>'
   '<path fill="url(#pb)" d="M63.4 16c-24 0-22 10.4-22 10.4l.03 10.8h22.4v3.2H32.6S16 38.6 16 63.9c0 25.2 14.5 24.3 14.5 24.3h7.9V77.1s-.43-14.5 14.3-14.5h22.2s13.8.22 13.8-13.3V29.6S102.5 16 63.4 16zM51 23.1a4 4 0 1 1 0 8.05 4 4 0 0 1 0-8.05z"/>'
   '<path fill="url(#py)" d="M64.6 112c24 0 22-10.4 22-10.4l-.03-10.8H64.2v-3.2h31.3s16.6 1.9 16.6-23.5c0-25.2-14.5-24.3-14.5-24.3h-7.9V51s.43 14.5-14.3 14.5H57.2s-13.8-.22-13.8 13.3v22.6S25.5 112 64.6 112zM77 104.9a4 4 0 1 1 0-8.05 4 4 0 0 1 0 8.05z"/></svg>',

 "txt": '<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 128 128">'
   '<path d="M30 10 h50 l24 24 v78 a6 6 0 0 1-6 6 H30 a6 6 0 0 1-6-6 V16 a6 6 0 0 1 6-6z" fill="#f8fafc" stroke="#cbd5e1" stroke-width="2.5"/>'
   '<path d="M80 10 v24 h24z" fill="#cbd5e1"/>'
   '<g stroke="#64748b" stroke-width="6" stroke-linecap="round"><line x1="42" y1="56" x2="90" y2="56"/><line x1="42" y1="72" x2="90" y2="72"/><line x1="42" y1="88" x2="74" y2="88"/></g></svg>',

 "url": '<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 128 128">' + _TILE.format(c="#0ea5e9") +
   '<g fill="none" stroke="#fff" stroke-width="10" stroke-linecap="round">'
   '<path d="M58 70 a16 16 0 0 1 0-22 l11-11 a16 16 0 0 1 23 23 l-5 5"/>'
   '<path d="M70 58 a16 16 0 0 1 0 22 l-11 11 a16 16 0 0 1-23-23 l5-5"/></g></svg>',

 "image": '<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 128 128">' + _TILE.format(c="#0891b2") +
   '<circle cx="46" cy="46" r="11" fill="#fde68a"/>'
   '<path d="M20 104 L52 62 L74 90 L88 76 L108 104 Z" fill="#083344"/></svg>',

 "video": '<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 128 128">' + _TILE.format(c="#dc2626") +
   '<path d="M50 40 L92 64 L50 88 Z" fill="#fff"/></svg>',

 "audio": '<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 128 128">' + _TILE.format(c="#7c3aed") +
   '<g fill="#fff"><rect x="70" y="36" width="8" height="50" rx="2"/>'
   '<path d="M78 36 q20 3 20 22 q-7-13-20-11 z"/>'
   '<ellipse cx="62" cy="86" rx="14" ry="11" transform="rotate(-18 62 86)"/></g></svg>',

 "dll": '<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 128 128">' + _TILE.format(c="#475569") +
   _gear_svg(64, 64, 30, 22, 10, 12, 16, "#fff", "#475569") + '</svg>',

 "exe": '<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 128 128">' + _TILE.format(c="#374151") +
   '<rect x="28" y="38" width="72" height="54" rx="7" fill="#fff"/>'
   '<circle cx="40" cy="49" r="3.2" fill="#ef4444"/><circle cx="51" cy="49" r="3.2" fill="#f59e0b"/><circle cx="62" cy="49" r="3.2" fill="#22c55e"/>'
   '<path d="M52 60 L78 72 L52 84 Z" fill="#374151"/></svg>',

 "zip": '<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 128 128">' + _TILE.format(c="#d97706") +
   '<rect x="57" y="16" width="14" height="96" fill="#fbbf24"/>'
   '<g fill="#78350f"><rect x="50" y="24" width="8" height="6"/><rect x="70" y="24" width="8" height="6"/>'
   '<rect x="50" y="38" width="8" height="6"/><rect x="70" y="38" width="8" height="6"/>'
   '<rect x="50" y="52" width="8" height="6"/><rect x="70" y="52" width="8" height="6"/></g>'
   '<rect x="54" y="66" width="20" height="26" rx="5" fill="#fef3c7"/>'
   '<rect x="61" y="72" width="6" height="12" rx="3" fill="#78350f"/></svg>',

 "file": '<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 128 128">'
   '<path d="M34 12 h44 l26 26 v78 a6 6 0 0 1-6 6 H34 a6 6 0 0 1-6-6 V18 a6 6 0 0 1 6-6z" fill="#60a5fa"/>'
   '<path d="M78 12 v26 h26z" fill="#2563eb"/></svg>',

 "folder": '<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 128 128">'
   '<path d="M16 34 a8 8 0 0 1 8-8 h26 l12 12 h40 a8 8 0 0 1 8 8 v10 H16 z" fill="#d97706"/>'
   '<path d="M16 46 h96 v50 a8 8 0 0 1-8 8 H24 a8 8 0 0 1-8-8 z" fill="#fbbf24"/></svg>',

 "code": '<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 128 128">' + _TILE.format(c="#6d28d9") +
   '<g fill="none" stroke="#fff" stroke-width="8" stroke-linecap="round" stroke-linejoin="round">'
   '<polyline points="46,48 28,64 46,80"/><polyline points="82,48 100,64 82,80"/></g>'
   '<line x1="73" y1="42" x2="57" y2="86" stroke="#c4b5fd" stroke-width="8" stroke-linecap="round"/></svg>',

 "bash": '<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 128 128">'
   '<rect x="8" y="8" width="112" height="112" rx="18" fill="#0d1117"/>'
   '<g fill="none" stroke="#4ade80" stroke-width="8" stroke-linecap="round" stroke-linejoin="round">'
   '<polyline points="36,50 54,66 36,82"/><line x1="64" y1="84" x2="92" y2="84"/></g></svg>',

 "html": '<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 128 128">' + _TILE.format(c="#0ea5e9") +
   '<g fill="none" stroke="#fff" stroke-width="6"><circle cx="64" cy="64" r="34"/>'
   '<ellipse cx="64" cy="64" rx="15" ry="34"/><line x1="30" y1="64" x2="98" y2="64"/>'
   '<line x1="39" y1="46" x2="89" y2="46" stroke-width="5"/><line x1="39" y1="82" x2="89" y2="82" stroke-width="5"/></g></svg>',
}
ICON_SVGS["default"] = ICON_SVGS["file"]

# Letter tiles: type -> (tile colour, letter, font-size ratio)
_LETTER_SPEC = {
    "word":  ("#185ABD", "W",   0.58),
    "excel": ("#107C41", "X",   0.60),
    "ppt":   ("#C43E1C", "P",   0.60),
    "pdf":   ("#C42B1C", "PDF", 0.30),
}


def _draw_letter_tile(icon_type: str, size: int, colour_hint: str = None) -> QPixmap:
    """PIL-drawn coloured tile with a letter (Office/PDF), the clipboard-
    text "Aa" symbol, or the dynamic hex-colour swatch. PIL loads the bold
    TTF directly, so the glyphs stay crisp where Qt's SVG can't draw text."""
    from PIL import ImageDraw
    img = Image.new("RGBA", (size * _SS, size * _SS), (0, 0, 0, 0))
    d   = _ScaledDraw(ImageDraw.Draw(img), _SS)

    if icon_type == "hex":
        col = (colour_hint or "").strip()
        if len(col) in (4, 5):      # #RGB / #RGBA -> #RRGGBB
            col = "#" + "".join(ch * 2 for ch in col[1:4])
        elif len(col) == 9:         # #RRGGBBAA -> drop alpha
            col = col[:7]
        try:
            r, g, b = (int(col[i:i+2], 16) for i in (1, 3, 5))
        except (ValueError, IndexError):
            r, g, b, col = 236, 72, 153, "#ec4899"
        d.rounded_rectangle([1, 1, size-1, size-1], radius=size*0.16, fill=col)
        d.rounded_rectangle([1, 1, size-1, size-1], radius=size*0.16,
                            outline="#00000040", width=1)
        fg = "#1e1e1e" if 0.299*r + 0.587*g + 0.114*b > 140 else "white"
        f = _bold_font(max(6, int(size*0.55)))
        if f:
            d.text((size/2, size*0.52), "#", font=f, fill=fg, anchor="mm")

    elif icon_type == "text":
        # Copied CHARACTERS (not a .txt file): font symbol, big "A" + small "a"
        d.rounded_rectangle([1, 1, size-1, size-1], radius=size*0.16, fill="#4f46e5")
        f_big   = _bold_font(max(6, int(size*0.62)))
        f_small = _bold_font(max(5, int(size*0.38)))
        if f_big and f_small:
            d.text((size*0.40, size*0.50), "A", font=f_big,   fill="white", anchor="mm")
            d.text((size*0.78, size*0.62), "a", font=f_small, fill="white", anchor="mm")

    else:
        col, letter, ratio = _LETTER_SPEC[icon_type]
        d.rounded_rectangle([1, 1, size-1, size-1], radius=size*0.16, fill=col)
        f = _bold_font(max(6, int(size*ratio)))
        if f:
            d.text((size/2, size*0.52), letter, font=f, fill="white", anchor="mm")

    img = img.resize((size, size), Image.LANCZOS)
    data = img.tobytes("raw", "RGBA")
    qimg = QImage(data, size, size, QImage.Format.Format_RGBA8888)
    return QPixmap.fromImage(qimg)


# True while a drag-and-drop is in flight. Auto-close paths (panel leave
# timers, hover-to-close polling) MUST stand down during a drag: QDrag.exec
# runs a nested event loop inside the source widget's mouse-handling stack,
# and destroying that widget mid-drag is a use-after-free hard crash.
_DRAG_STATE = {"active": False}

_TEXT_KINDS = ("text", "url", "code", "bash", "hex")


def _mime_for_items(items: list) -> QMimeData:
    """Build drag-and-drop payload for one or more clipboard items.

    Files and images travel as file URLs (dropping on Explorer copies
    them; editors take the paths), text kinds travel as plain text.
    A mixed selection carries both — the drop target picks what it
    understands.
    """
    md = QMimeData()
    urls, texts = [], []
    for it in items:
        t = it.get("type")
        c = it.get("content")
        if t == "file" and isinstance(c, list):
            urls.extend(QUrl.fromLocalFile(p) for p in c)
        elif t == "image":
            urls.append(QUrl.fromLocalFile(str(c)))
        else:
            texts.append(str(c))
    if urls:
        md.setUrls(urls)
    if texts:
        md.setText("\n".join(texts))
    return md


def _content_count(item: dict):
    """How many things are 'inside' a file item, or None if not applicable.

    Multi-file entry → number of files in it.
    Single folder entry → number of entries inside the folder on disk.
    Single plain file → None (no count shown).
    """
    if item.get("type") != "file":
        return None
    content = item.get("content")
    if not isinstance(content, list) or not content:
        return None
    if len(content) > 1:
        return len(content)
    if os.path.isdir(content[0]):
        try:
            return len(os.listdir(content[0]))
        except OSError:
            return None
    return None


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
    sig_select  = pyqtSignal(object, object)  # item, row — Ctrl+click toggle
    sig_drag    = pyqtSignal(object, object)  # item, row — drag threshold hit

    def __init__(self, item: dict, history, profiles, colours: dict, parent=None):
        super().__init__(parent)
        # QWidget SUBCLASSES don't paint stylesheet backgrounds unless
        # this attribute is set. Rows used to inherit their background
        # from the popup's window-level stylesheet; the phase-1 card
        # scoped that stylesheet away, so rows must self-paint now.
        self.setAttribute(Qt.WidgetAttribute.WA_StyledBackground, True)
        self.item     = item
        self.history  = history
        self.profiles = profiles
        self.C        = colours
        # Eased hover animation. OutExpo ≈ the old exponential-chase lerp:
        # instant response, long soft landing — the "fluid" feel.
        self._anim_t = 0.0
        self._anim   = QVariantAnimation(self)
        self._anim.setDuration(250)
        self._anim.setEasingCurve(QEasingCurve.Type.OutExpo)
        self._anim.valueChanged.connect(self._on_anim_value)

        # Drag / selection state
        self._press_pos    = None
        self._is_dragging  = False
        self._drag_started = False
        self._selected     = False

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

        self._orig_base = self._base_bg   # kept — selection tints from this

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

        # Content count badge — how many files in a multi-file entry, or
        # how many items inside a single copied folder.
        cnt = _content_count(item)
        if cnt is not None:
            badge = QLabel(str(cnt), self)
            badge.setFont(QFont("Segoe UI", 8, QFont.Weight.Bold))
            badge.setStyleSheet(
                f"color:{C['text']};background:{C['bg_hover']};"
                f"border-radius:9px;padding:1px 7px;")
            badge.setToolTip(f"{cnt} items")
            cnt_col = QVBoxLayout()
            cnt_col.setContentsMargins(0, 0, 4, 0)
            cnt_col.addStretch()
            cnt_col.addWidget(badge)
            cnt_col.addStretch()
            main.addLayout(cnt_col)

        # Action buttons grid  📌 ↑ / ✕ ↓
        btn_col = QVBoxLayout()
        btn_col.setContentsMargins(0, 6, 6, 6)
        btn_col.setSpacing(2)

        row1 = QHBoxLayout(); row1.setSpacing(2)
        row2 = QHBoxLayout(); row2.setSpacing(2)
        # Pin: yellow outline (no fill) when unpinned, solid red when pinned.
        pin_col = C["danger"] if pinned else C["pin"]
        for text, sig, colour, row in [
            ("pin", self.sig_pin,     pin_col,       row1),
            ("↑",   self.sig_move_up, C["text_dim"], row1),
            ("✕",   self.sig_delete,  C["danger"],   row2),
            ("↓",   self.sig_move_dn, C["text_dim"], row2),
        ]:
            btn = _ActionButton("" if text == "pin" else text, colour, C, self)
            if text == "pin":
                btn.setPixmap(_pin_pixmap(colour, filled=pinned))
                btn.setToolTip("Unpin" if pinned else "Pin")
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
        if itype == "hex":
            # Swatch of the ACTUAL colour the hex code names
            label.setPixmap(_icon_pixmap("hex", THUMB_SIZE,
                                         colour_hint=str(item.get("content","")).strip()))
            return
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
        ext = None
        if itype == "file":
            files = item.get("content",[])
            if isinstance(files, list) and files:
                ext = os.path.splitext(files[0])[1].lower()
                icon_type = _FILE_TYPE_MAP.get(ext, "file")
                if len(files) > 1:
                    icon_type = "file"   # multi-file entry: generic icon
                    ext = None
                elif os.path.isdir(files[0]):
                    icon_type = "folder"
                    ext = None
            else:
                icon_type = "file"
        else:
            icon_type = itype or "file"
        label.setPixmap(_icon_pixmap(icon_type, THUMB_SIZE, ext=ext))

    # ── Background ───────────────────────────────────────────────────────────

    def _apply_bg(self, hex_col: str):
        # Selected rows carry an accent outline on top of their tint
        border = (f"border:1px solid {self.C['accent']};" if self._selected
                  else "border:none;")
        self.setStyleSheet(f"background:{hex_col};{border}")
        # Keep labels transparent so row bg shows through
        for lbl in [self._preview_lbl, self._source_lbl, self._thumb]:
            lbl.setStyleSheet(lbl.styleSheet().split(";")[0] + ";background:transparent;")

    # ── Multi-selection (Ctrl+click) ─────────────────────────────────────────

    def set_selected(self, selected: bool):
        self._selected = selected
        self._base_bg  = (_hex_lerp(self._orig_base, self.C["accent"], 0.28)
                          if selected else self._orig_base)
        # Repaint at the current hover state
        self._apply_bg(_hex_lerp(self._base_bg, self.C["bg_hover"], self._anim_t))

    # ── Hover animation ──────────────────────────────────────────────────────

    def _enter_hover(self):
        self._animate_to(1.0)

    def _leave_hover(self):
        self._animate_to(0.0)

    def _animate_to(self, target: float):
        self._anim.stop()
        self._anim.setStartValue(self._anim_t)
        self._anim.setEndValue(target)
        self._anim.start()

    def _on_anim_value(self, v):
        t = self._anim_t = float(v)
        # Three cheap stylesheet updates per frame — nothing heavier.
        # (A QGraphicsDropShadowEffect glow was tried here: it forces the
        # row to re-rasterize through a blur EVERY frame, which visibly
        # janks the animation. Never attach effects to animated rows.)
        bg = _hex_lerp(self._base_bg, self.C["bg_hover"], t)
        self._apply_bg(bg)
        self._strip.setFixedWidth(max(3, int(3 + 7 * t)))
        tc = _hex_lerp(self.C["text_preview"], self.C["text"], t)
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
            self._press_pos    = event.globalPosition().toPoint()
            self._is_dragging  = False
            self._drag_started = False
            if event.modifiers() & Qt.KeyboardModifier.ControlModifier:
                # Ctrl+click — toggle multi-selection, never paste
                itm = self.item
                QTimer.singleShot(0, lambda: self.sig_select.emit(itm, self))
        elif event.button() == Qt.MouseButton.RightButton:
            pt  = event.globalPosition().toPoint()
            itm = self.item
            QTimer.singleShot(0, lambda: self.sig_rclick.emit(itm, pt))
        try:
            super().mousePressEvent(event)
        except RuntimeError:
            pass

    def mouseMoveEvent(self, event):
        if self._press_pos and event.buttons() & Qt.MouseButton.LeftButton:
            delta = event.globalPosition().toPoint() - self._press_pos
            if not self._is_dragging and (abs(delta.x()) > 6 or abs(delta.y()) > 6):
                self._is_dragging = True
                if not self._drag_started:
                    # Start a real OS drag — synchronously, inside the move
                    # handler (the standard Qt drag-and-drop pattern).
                    self._drag_started = True
                    self.sig_drag.emit(self.item, self)
        try:
            super().mouseMoveEvent(event)
        except RuntimeError:
            pass

    def mouseReleaseEvent(self, event):
        if event.button() == Qt.MouseButton.LeftButton:
            ctrl = bool(event.modifiers() & Qt.KeyboardModifier.ControlModifier)
            if not self._is_dragging and not ctrl:
                itm = self.item
                QTimer.singleShot(0, lambda: self.sig_paste.emit(itm))
            self._press_pos    = None
            self._is_dragging  = False
            self._drag_started = False
        try:
            super().mouseReleaseEvent(event)
        except RuntimeError:
            pass


def _pin_pixmap(colour: str, filled: bool, px: int = 16) -> QPixmap:
    """Draw a classic 📌-style pushpin (angled, ball head + collar + needle).

    The real 📌 emoji renders as a COLOR emoji on Windows — the stylesheet
    `color:` property is ignored, so its colour can't reflect pin state.
    Drawing the same shape ourselves makes the colour real: transparent
    with a coloured border when unpinned, solid fill when pinned.
    """
    pm = QPixmap(px, px)
    pm.fill(Qt.GlobalColor.transparent)
    p = QPainter(pm)
    p.setRenderHint(QPainter.RenderHint.Antialiasing)
    col = QColor(colour)
    pen = QPen(col)
    pen.setWidthF(max(1.2, px / 12))
    p.setPen(pen)
    p.setBrush(QBrush(col) if filled else Qt.BrushStyle.NoBrush)

    # Draw a vertical pushpin in a canvas rotated 45° clockwise —
    # head ends upper-right, needle tip lower-left, like 📌.
    p.translate(px * 0.5, px * 0.5)
    p.rotate(45)
    s = px / 16.0   # design units on a 16-unit grid
    p.drawEllipse(QRectF(-2.9*s, -7.2*s, 5.8*s, 5.8*s))       # ball head
    p.drawPolygon(QPolygonF([                                  # collar
        QPointF(-1.9*s, -1.6*s), QPointF( 1.9*s, -1.6*s),
        QPointF( 2.9*s,  1.4*s), QPointF(-2.9*s,  1.4*s),
    ]))
    p.drawLine(QPointF(0, 1.4*s), QPointF(0, 7.2*s))           # needle
    p.end()
    return pm


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
    """Small transient notification near the popup / cursor.

    Deliberately unobtrusive: on screen for AT MOST 1.5 seconds (fade
    included), click-through so it can never intercept a click, and never
    takes focus.
    """

    MAX_MS = 1500   # hard ceiling — no notification lives longer than 1.5 s

    def __init__(self, message: str, parent_popup=None, duration: int = 1500):
        super().__init__(None, Qt.WindowType.FramelessWindowHint |
                                Qt.WindowType.WindowStaysOnTopHint |
                                Qt.WindowType.Tool |
                                Qt.WindowType.WindowTransparentForInput)
        self.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground)
        self.setAttribute(Qt.WidgetAttribute.WA_ShowWithoutActivating)
        self.setAttribute(Qt.WidgetAttribute.WA_DeleteOnClose)

        lbl = QLabel(message, self)
        lbl.setFont(QFont("Segoe UI", 18))
        lbl.setStyleSheet("color:#e2e8f0;background:#1c1c2a;"
                          "border-radius:10px;padding:10px 24px;")

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
        self.setWindowOpacity(0.85)
        self.show()

        self._alpha = 0.85
        self._fade_timer = QTimer(self)
        self._fade_timer.timeout.connect(self._fade_step)
        # Fade takes ~250 ms — start early enough that the toast is GONE
        # by `duration`, which is itself capped at 1 s.
        duration = min(duration, self.MAX_MS)
        QTimer.singleShot(max(0, duration - 250), self._start_fade)

    def _start_fade(self):
        self._fade_timer.start(40)

    def _fade_step(self):
        self._alpha -= 0.14
        if self._alpha <= 0:
            self._fade_timer.stop()
            self.close()   # WA_DeleteOnClose → destroyed signal fires
        else:
            self.setWindowOpacity(self._alpha)


# ── Side panel (multi-file list) ──────────────────────────────────────────────

# Custom data roles for side-panel rows (read by _PinDelegate)
_PIN_ROLE   = Qt.ItemDataRole.UserRole + 1   # bool — row is pinned
_COUNT_ROLE = Qt.ItemDataRole.UserRole + 2   # int  — items inside a folder row


class _PinDelegate(QStyledItemDelegate):
    """Paints right-edge decorations on side-panel rows: a red pin for
    pinned rows and a dim item-count for folder rows (count sits left of
    the pin when both are present). QListWidgetItem only supports one
    (left) icon slot — the file-type icon lives there, so these markers
    have to be painted by a delegate."""

    PIN_PX = 11

    def __init__(self, colours: dict, parent=None):
        super().__init__(parent)
        self._pin = _pin_pixmap(colours["danger"], filled=True, px=self.PIN_PX)
        self._dim = QColor(colours["text_dim"])

    def paint(self, painter, option, index):
        super().paint(painter, option, index)
        r = option.rect
        x_right = r.right() - 5
        if index.data(_PIN_ROLE):
            x = r.right() - self.PIN_PX - 5
            y = r.top() + (r.height() - self.PIN_PX) // 2
            painter.drawPixmap(x, y, self._pin)
            x_right = x - 4
        cnt = index.data(_COUNT_ROLE)
        if cnt is not None:
            painter.save()
            painter.setPen(self._dim)
            f = painter.font()
            f.setPointSize(7)
            painter.setFont(f)
            painter.drawText(
                QRect(x_right - 34, r.top(), 34, r.height()),
                Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter,
                str(cnt))
            painter.restore()


class SidePanelWidget(QWidget):
    """Floating panel to the right of the popup listing files in a multi-file item."""

    PANEL_W     = 280
    ROW_H       = 26    # compact rows — smaller font, more files in view
    MAX_VISIBLE = 10    # first 10 files visible; scrolling reveals the rest

    def __init__(self, files: list, item: dict, history, colours: dict,
                 on_paste_file, parent_popup, parent=None, controller=None,
                 parent_panel=None, title=None):
        super().__init__(None, Qt.WindowType.FramelessWindowHint |
                                Qt.WindowType.WindowStaysOnTopHint |
                                Qt.WindowType.Tool)
        self.setAttribute(Qt.WidgetAttribute.WA_ShowWithoutActivating)
        # MUST come before winId() below — translucency only applies if
        # set before the native window is created.
        self.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground)
        _set_no_activate(int(self.winId()))

        self.files    = files
        self.item     = item
        self.history  = history
        self.C        = colours
        self.on_paste_file = on_paste_file
        self._parent_popup = parent_popup
        self.controller    = controller     # DropdownPopup — profiles/toast/refresh
        self._parent_panel = parent_panel   # SidePanelWidget that spawned us (nested)
        self._sub_panel    = None           # child panel for a hovered folder row
        self._folder       = None           # folder this panel lists (nested only)
        self._title        = title
        self._menu_open    = False          # suppress leave-close while a menu shows
        self._last_btn     = Qt.MouseButton.LeftButton
        self._sel_at_press = []             # selection snapshot (see eventFilter)
        self._close_timer  = QTimer(self)
        self._close_timer.setSingleShot(True)
        self._close_timer.timeout.connect(self._close_if_cursor_outside)

        # Rounded card + Qt drop shadow inside transparent margins —
        # same elevation recipe as the main popup. Same INVARIANT too:
        # blur + |offset| must fit inside the margins or layered-window
        # updates get rejected and the panel freezes.
        outer = QVBoxLayout(self)
        outer.setContentsMargins(14, 10, 14, 17)
        card = QWidget(self)
        card.setObjectName("panel_card")
        card.setStyleSheet(
            f"QWidget#panel_card {{background:{colours['bg']};"
            f"border:1px solid {colours['border']};border-radius:8px;}}")
        _shadow = QGraphicsDropShadowEffect(card)
        _shadow.setBlurRadius(11)     # 11 + offset 2 < margins (14/10/17)
        _shadow.setOffset(0, 2)
        _shadow.setColor(QColor(0, 0, 0, 140))
        card.setGraphicsEffect(_shadow)
        outer.addWidget(card)

        lay = QVBoxLayout(card)
        lay.setContentsMargins(1, 1, 1, 7)   # bottom pad = rounded base
        lay.setSpacing(0)

        # Header row — title plus a "✕ clear" badge that appears while a
        # Ctrl+click multi-selection is active
        hdr_text = (f"  {title} — {len(files)} files" if title
                    else f"  {len(files)} files")
        hdr_row = QWidget(self)
        hdr_row.setFixedHeight(28)
        hdr_row.setStyleSheet(
            f"background:{_grad_v(colours['accent_light'], _shade(colours['accent'], -0.18))};"
            f"border-top-left-radius:7px;"
            f"border-top-right-radius:7px;"
            f"border-bottom:1px solid rgba(0,0,0,90);")
        hl = QHBoxLayout(hdr_row)
        hl.setContentsMargins(6, 0, 8, 0)
        hl.setSpacing(6)

        hdr = QLabel(hdr_text, hdr_row)
        hdr.setFont(QFont("Segoe UI", 9, QFont.Weight.Bold))
        hdr.setStyleSheet("color:white;background:transparent;")
        hl.addWidget(hdr)
        hl.addStretch()
        self._hdr = hdr   # kept so per-file delete can update the count live

        badge = QLabel("", hdr_row)
        badge.setFont(QFont("Segoe UI", 8, QFont.Weight.Bold))
        badge.setStyleSheet("color:white;background:transparent;")
        badge.setCursor(Qt.CursorShape.PointingHandCursor)
        badge.setToolTip("Clear selection")
        badge.mousePressEvent = lambda e: self._list.clearSelection()
        badge.hide()
        hl.addWidget(badge)
        self._sel_badge = badge

        lay.addWidget(hdr_row)

        # Scrollable list — Ctrl+click multi-select. (Drag-out was tried
        # here and scrapped: the low-level mouse hook adds per-event
        # latency that makes native list drags lag badly.)
        self._list = QListWidget(self)
        self._list.setSelectionMode(
            QAbstractItemView.SelectionMode.ExtendedSelection)
        self._list.itemSelectionChanged.connect(self._on_selection_changed)
        self._list.setStyleSheet(f"""
            QListWidget {{ background:{colours['bg']}; border:none; outline:none; }}
            QListWidget::item {{ height:{self.ROW_H}px; color:{colours['text']};
                                 font-size:11px; padding-left:6px;
                                 padding-right:36px; /* clear of count + pin */ }}
            QListWidget::item:hover {{ background:{colours['bg_hover']}; }}
            QListWidget::item:selected {{ background:{colours['bg_hover']}; }}
        """ + _scrollbar_qss(colours))
        self._list.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        self._list.setFixedWidth(self.PANEL_W)
        self._list.setIconSize(QSize(16, 16))
        self._list.setItemDelegate(_PinDelegate(colours, self._list))
        max_visible = min(len(files), self.MAX_VISIBLE)
        self._list.setFixedHeight(max_visible * self.ROW_H)
        self._list.itemClicked.connect(self._on_file_click)

        # Right-click menu per file (Send to profile / Pin / Delete)
        self._list.setContextMenuPolicy(Qt.ContextMenuPolicy.CustomContextMenu)
        self._list.customContextMenuRequested.connect(self._show_file_menu)
        # Record which button was pressed: Qt emits itemClicked for ANY
        # mouse button, so without this a right-click would also paste.
        self._list.viewport().installEventFilter(self)

        # Hovering a FOLDER row reveals its contents in a nested panel.
        # itemEntered needs mouse tracking on the viewport specifically.
        self._list.viewport().setMouseTracking(True)
        self._list.itemEntered.connect(self._on_item_hover)

        self._populate_rows()

        lay.addWidget(self._list)
        self.adjustSize()

        # Mouse-leave timer management
        self._list.setMouseTracking(True)
        self.setMouseTracking(True)

    def eventFilter(self, obj, ev):
        if ev.type() == QEvent.Type.MouseButtonPress:
            self._last_btn = ev.button()
            if (ev.button() == Qt.MouseButton.LeftButton
                    and not (ev.modifiers() & Qt.KeyboardModifier.ControlModifier)):
                # Snapshot the multi-selection BEFORE Qt handles the press:
                # ExtendedSelection collapses the selection to the clicked
                # row on plain press, and itemClicked only fires afterwards.
                # Without this, "click a selected row → paste all selected"
                # would always see a single-item selection.
                self._sel_at_press = [
                    self._list.item(i).data(Qt.ItemDataRole.UserRole)
                    for i in range(self._list.count())
                    if self._list.item(i).isSelected()]
        return False   # never consume — just observe

    def _on_selection_changed(self):
        """Show the header '✕ clear' badge while files are selected."""
        n = len(self._list.selectedItems())
        if n:
            self._sel_badge.setText(f"✕ {n} selected")
            self._sel_badge.show()
        else:
            self._sel_badge.hide()

    def _on_file_click(self, item: QListWidgetItem):
        # itemClicked fires for right-clicks too — those open the menu,
        # they must not paste.
        if self._last_btn != Qt.MouseButton.LeftButton:
            return
        # Ctrl+click is a selection toggle (ExtendedSelection), not a paste
        if QApplication.keyboardModifiers() & Qt.KeyboardModifier.ControlModifier:
            return
        fp  = item.data(Qt.ItemDataRole.UserRole)
        # Clicking a row that was part of the multi-selection pastes ALL
        # selected files (selection order = visible list order). The
        # snapshot from eventFilter is used because Qt collapsed the real
        # selection on mouse-press.
        sel = self._sel_at_press
        self._sel_at_press = []
        paths = sel if (len(sel) > 1 and fp in sel) else [fp]
        self.close()
        # CRITICAL: defer the paste until this mouse-release event has fully
        # unwound. on_paste_file → _paste_item → _do_hide drops the last
        # Python reference to this panel, which immediately deletes the
        # C++ widget tree — including the QListWidget whose event handler
        # we are inside right now. Calling it synchronously is a
        # use-after-free: the app hard-crashes with no Python traceback.
        # QTimer.singleShot(0) runs the paste after the stack unwinds.
        # Capture the callback locally so the lambda holds no reference
        # to this (soon to be deleted) panel.
        cb = self.on_paste_file
        QTimer.singleShot(0, lambda: cb(paths))

    def arm_close_timer(self):
        # While a context menu is open the mouse "leaves" the panel —
        # that must not close it out from under the menu.
        if self._menu_open:
            return
        self._close_timer.start(250)

    def _close_if_cursor_outside(self):
        """Close-timer target: close only if the cursor has truly left.

        The countdown can be armed by HANDOFFS — e.g. a closing child
        panel re-arms its parent — while the cursor is still sitting
        inside this panel. enterEvent won't re-fire (the mouse never
        left), so cancelling can't save us; the timeout itself must
        re-verify before killing the window. Without this, hovering a
        non-folder row in the side list closed the child AND then the
        side list out from under the cursor."""
        if _DRAG_STATE["active"]:
            return   # NEVER destroy the drag-source window mid-drag
        try:
            gp = QCursor.pos()
            if self.isVisible() and self.frameGeometry().contains(gp):
                return   # cursor is inside me — stay open
            sub = self._sub_panel
            if (sub is not None and sub.isVisible()
                    and sub.frameGeometry().contains(gp)):
                return   # cursor is inside my child panel — stay open
        except RuntimeError:
            return       # C++ widget already gone — nothing to close
        self.close()

    def cancel_close_timer(self):
        self._close_timer.stop()

    def enterEvent(self, e):
        # Entering any panel keeps the WHOLE ancestor chain alive —
        # otherwise the parent's leave-timer closes it (and us with it)
        # while the mouse is in a nested folder panel.
        self.cancel_close_timer()
        p = self._parent_panel
        while p is not None:
            try:
                p.cancel_close_timer()
            except RuntimeError:
                break   # ancestor C++ object already deleted
            p = p._parent_panel
        super().enterEvent(e)

    def leaveEvent(self, e):
        self.arm_close_timer()
        super().leaveEvent(e)

    def closeEvent(self, e):
        # Closing a panel closes its nested children with it, and hands
        # the close countdown back to the parent (harmless if the parent
        # itself is the one closing us).
        if self._sub_panel:
            try:
                self._sub_panel.close()
            except Exception:
                pass
            self._sub_panel = None
        if self._parent_panel is not None:
            try:
                self._parent_panel.arm_close_timer()
            except RuntimeError:
                pass
        super().closeEvent(e)

    # ── Nested folder panels ─────────────────────────────────────────────────

    def _on_item_hover(self, qi: QListWidgetItem):
        # Only the FIRST-level side list reveals folder contents. A child
        # panel never spawns grandchildren — one level of drill-down max.
        if self._parent_panel is not None:
            return
        fp = qi.data(Qt.ItemDataRole.UserRole)
        if fp and os.path.isdir(fp):
            self._open_sub_panel(qi, fp)
        elif self._sub_panel:
            # Hovered a non-folder row — let the open child wind down
            self._sub_panel.arm_close_timer()

    def _open_sub_panel(self, qi: QListWidgetItem, folder: str):
        if self._sub_panel and self._sub_panel._folder == folder:
            self._sub_panel.cancel_close_timer()   # already showing it
            return
        if self._sub_panel:
            try:
                self._sub_panel.close()
            except Exception:
                pass
            self._sub_panel = None

        try:
            names = sorted(os.listdir(folder))
        except OSError:
            return   # unreadable / vanished folder — nothing to reveal
        files = [os.path.join(folder, n) for n in names]
        if not files:
            return

        sub = SidePanelWidget(files, self.item, self.history, self.C,
                              self.on_paste_file, self._parent_popup,
                              controller=self.controller, parent_panel=self,
                              title=os.path.basename(folder))
        sub._folder = folder
        self._sub_panel = sub

        # Same smart side-picking as the main popup's panel, relative to us
        pw, ph = sub.width(), sub.height()
        my     = self.geometry()
        screen = QApplication.screenAt(my.center()) or QApplication.primaryScreen()
        g = screen.availableGeometry()
        space_right = g.right() - my.right()
        space_left  = my.left() - g.left()
        # Overlap the transparent shadow margins (14px each side) so the
        # visible cards sit ~2px apart with no dead zone for the cursor.
        if space_right >= pw or space_right >= space_left:
            px = my.right() - 26
        else:
            px = my.left() - pw + 26
        px = max(g.left(), min(px, g.right() - pw))
        # Align with the hovered row, clamped on-screen
        row_top = self._list.viewport().mapToGlobal(
            self._list.visualItemRect(qi).topLeft())
        py = max(g.top(), min(row_top.y(), g.bottom() - ph))
        sub.move(px, py)
        sub.show()

    # ── Per-file right-click menu ────────────────────────────────────────────

    def _show_file_menu(self, pos):
        qi = self._list.itemAt(pos)
        ctrl = self.controller
        if qi is None or ctrl is None:
            return
        fp = qi.data(Qt.ItemDataRole.UserRole)
        C  = self.C

        self._menu_open = True
        self.cancel_close_timer()
        try:
            menu = QMenu(self)
            menu.setStyleSheet(f"""
                QMenu {{ background:{C['bg_item']}; color:{C['text']};
                         border:1px solid {C['border']}; font-family:'Segoe UI'; }}
                QMenu::item:selected {{ background:{C['bg_hover']}; }}
            """)

            # Send to profile ▸ — ALL profiles are valid targets here,
            # including the active one and General. Unlike a main-list
            # item, a file inside a multi-file entry is not individually
            # IN any profile yet — sending it to General creates its own
            # visible entry there; to a named profile, a hidden one.
            profs = self._send_targets()
            if profs:
                sub = menu.addMenu("Send to profile")
                for prof in profs:
                    act = sub.addAction(prof["name"])
                    act.setData(("send", prof["id"], prof["name"]))

            pin_act = menu.addAction("Unpin" if self._file_is_pinned(fp) else "Pin")
            pin_act.setData(("pin", None, None))
            # Delete only applies to files that ARE entries of the clipboard
            # item — not to files inside a hovered folder (nested panel).
            if fp in (self.item.get("content") or []):
                del_act = menu.addAction("Delete file")
                del_act.setData(("delete", None, None))

            _activate_for_menu(self)   # menu needs an ACTIVE owner to grab
            chosen = menu.exec(self._list.viewport().mapToGlobal(pos))
        finally:
            self._menu_open = False
            # Re-arm the leave-close only if the cursor has left the panel
            if not self.rect().contains(self.mapFromGlobal(QCursor.pos())):
                self.arm_close_timer()

        if not chosen or not chosen.data():
            return
        action, prof_id, prof_name = chosen.data()
        if action == "send":
            self._send_file_to_profile(fp, prof_id, prof_name)
        elif action == "pin":
            self._toggle_file_pin(fp)
        elif action == "delete":
            self._delete_file(fp)

    # ── Row rendering (pin-aware) ────────────────────────────────────────────

    def _populate_rows(self):
        """(Re)fill the list: pinned files first, marked by a red pin at the
        row's RIGHT edge (painted by _PinDelegate via _PIN_ROLE data).
        QListWidgetItems are lightweight (not widgets) and the type icons
        are cached, so a full repopulate is instant even for 247 files."""
        self._list.clear()
        pinned = [f for f in self.files if self._file_is_pinned(f)]
        normal = [f for f in self.files if not self._file_is_pinned(f)]
        for fp in pinned + normal:
            basename = os.path.basename(fp)
            ext      = os.path.splitext(fp)[1].lower()
            itype    = _FILE_TYPE_MAP.get(ext, "folder" if os.path.isdir(fp) else "file")
            qi       = QListWidgetItem(f"  {basename}")
            qi.setData(Qt.ItemDataRole.UserRole, fp)
            qi.setData(_PIN_ROLE, fp in pinned)
            row_ext = None if itype == "folder" else ext
            if itype == "folder":
                try:
                    qi.setData(_COUNT_ROLE, len(os.listdir(fp)))
                except OSError:
                    pass   # unreadable folder — no count shown
            qi.setIcon(QIcon(_icon_pixmap(itype, 16, ext=row_ext)))
            self._list.addItem(qi)

    def _row_of(self, fp: str) -> int:
        """Row index of a file in DISPLAY order (≠ self.files order once
        pinned files are sorted to the top)."""
        for i in range(self._list.count()):
            if self._list.item(i).data(Qt.ItemDataRole.UserRole) == fp:
                return i
        return -1

    # ── Per-file actions ─────────────────────────────────────────────────────

    def _file_is_pinned(self, fp: str) -> bool:
        # Pin state lives ON the multi-file entry itself ("pinned_files")
        # — side-list specific, never touches the main list.
        return fp in self.item.get("pinned_files", [])

    def _toggle_file_pin(self, fp: str):
        pf = self.item.setdefault("pinned_files", [])
        if fp in pf:
            pf.remove(fp)
        else:
            pf.append(fp)
        self.controller.history._save_history()   # item dict lives in history
        self._populate_rows()   # re-sort: pinned to top, badge on/off

    def _send_targets(self) -> list:
        """Profiles offered in the per-file 'Send to profile' submenu."""
        ctrl = self.controller
        if ctrl is None or not getattr(ctrl, "profiles", None):
            return []
        return ctrl.profiles.get_all_profiles()

    def _send_file_to_profile(self, fp: str, profile_id: str, profile_name: str):
        # Single files sent to a profile become their own history entries
        # (id = md5 of path). Named profiles keep them hidden from General;
        # sending to GENERAL itself un-hides the entry instead.
        ctrl  = self.controller
        hist  = ctrl.history
        fid   = hashlib.md5(fp.encode()).hexdigest()
        entry = hist._find_by_id(fid)
        if entry is None:
            entry = {
                "id":      fid,
                "type":    "file",
                "content": [fp],
                "source":  os.path.dirname(fp),
                "pinned":  False,
                "hidden":  True,
            }
            hist.items.insert(0, entry)
        if profile_id == "general":
            entry["hidden"] = False
        else:
            ctrl.profiles.add_item_to_profile(fid, profile_id)
        hist._save_history()
        ctrl._show_toast(f'Sent "{os.path.basename(fp)}" to "{profile_name}"')
        ctrl._refresh()

    def _delete_file(self, fp: str):
        ctrl = self.controller
        # Row index in display order, BEFORE any mutation (self.files may be
        # the same list object item["content"] that the data call mutates).
        idx = self._row_of(fp)
        pf = self.item.get("pinned_files", [])
        if fp in pf:
            pf.remove(fp)   # persisted by remove_file_from_item's save
        still_exists = ctrl.history.remove_file_from_item(self.item["id"], fp)
        if fp in self.files:
            self.files.remove(fp)
        if idx >= 0:
            self._list.takeItem(idx)
        self._hdr.setText(f"  {len(self.files)} files")
        if not still_exists or not self.files:
            self.close()   # whole entry gone — nothing left to show
        ctrl._refresh()


# ── Main popup window ─────────────────────────────────────────────────────────

class _PopupSignals(QObject):
    """Signals for thread-safe cross-thread calls into DropdownPopup.
    Emitting a signal from any thread safely invokes the connected slot
    on the thread that owns the QObject (the Qt main thread).
    """
    show_sig = pyqtSignal(int, int)   # x, y
    hide_sig = pyqtSignal()
    esc_sig  = pyqtSignal()           # Escape pressed (global keyboard hook —
                                      # QShortcut needs an ACTIVE window and
                                      # the popup is WS_EX_NOACTIVATE)


class _PasteWorker(QThread):
    """Runs the entire paste sequence off the Qt main thread.

    The paste sequence is inherently slow: it waits for the popup to hide
    and focus to return to the target app (~250 ms), converts images to
    BMP via PIL, sends Ctrl+V through pyautogui (which sleeps ~100 ms per
    key event), then waits 500 ms before un-pausing the clipboard watcher.
    Run on the main thread this froze every button and repaint for ~1 s.

    Win32 clipboard API and SendInput (pyautogui) are both thread-agnostic,
    so the whole sequence is safe on a worker thread. The watcher's
    `paused` / `last_seen` are plain attribute writes (GIL-atomic).

    Signals:
        failed(str) — emitted with an error message if the paste failed.
    """
    failed = pyqtSignal(str)

    def __init__(self, item: dict, watcher, paste_target, parent=None):
        super().__init__(parent)
        self._item   = item
        self._watch  = watcher
        self._target = paste_target   # hwnd captured on the main thread

    def run(self):
        item = self._item
        # Brief settle delay: lets the click's release event finish and any
        # transient window (side panel) close. The popup itself stays open
        # and never holds focus (WS_EX_NOACTIVATE), so no need to wait for
        # focus to return. Sleeping here is free — the UI keeps running.
        time.sleep(0.1)

        if self._watch:
            self._watch.paused = True
        try:
            win32clipboard.OpenClipboard()
            win32clipboard.EmptyClipboard()
            if item["type"] in ("text", "url", "code", "bash", "hex"):
                win32clipboard.SetClipboardData(win32con.CF_UNICODETEXT, item["content"])
                if self._watch:
                    self._watch.last_seen = hashlib.md5(
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
                    if self._watch:
                        self._watch.last_seen = hashlib.md5(
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
            try:
                win32clipboard.CloseClipboard()
            except Exception:
                pass
            if self._watch:
                self._watch.paused = False
            self.failed.emit(str(e))
            return

        # Restore the paste target's focus before sending Ctrl+V.
        # Normally the popup never takes focus (WS_EX_NOACTIVATE) and the
        # target is already foreground — but if the user typed in the
        # search box, the popup was activated and now HOLDS focus; without
        # this hand-back the Ctrl+V would land in the popup, not the app.
        # (Also covers the desktop Progman/WorkerW case.)
        if self._target:
            try:
                if win32gui.GetForegroundWindow() != self._target:
                    win32gui.SetForegroundWindow(self._target)
                    win32gui.BringWindowToTop(self._target)
                    time.sleep(0.15)
            except Exception:
                pass

        pyautogui.hotkey("ctrl", "v")

        if self._watch:
            # Let the target app read the clipboard before the watcher
            # resumes, so ClipDrop doesn't re-capture its own paste.
            time.sleep(0.5)
            try:
                if item["type"] in ("text", "url", "code", "bash", "hex"):
                    self._watch.last_seen = hashlib.md5(
                        item["content"].encode("utf-8")).hexdigest()
                elif item["type"] == "file":
                    self._watch.last_seen = hashlib.md5(
                        str(item["content"]).encode("utf-8")).hexdigest()
            except Exception:
                pass
            self._watch.paused = False


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
        self._paste_worker = None  # _PasteWorker QThread while a paste runs
        self._hover_timer = None   # cursor poll for hover-to-close mode
        self._hover_seen_inside = False
        self._selected_ids = set() # Ctrl+click multi-selection (item ids)
        self._colours     = DARK   # Current theme dict

        # Thread-safe signals — connected to slots that run on this object's thread
        self._sig = _PopupSignals()
        self._sig.show_sig.connect(self._build_and_show)
        self._sig.hide_sig.connect(self._do_hide)
        self._sig.esc_sig.connect(self._on_escape)
        # Global Escape (unsuppressed — other apps still get theirs).
        # A QShortcut can't do this job: it needs an active window and
        # the popup never activates.
        try:
            keyboard.add_hotkey("esc", self._sig.esc_sig.emit, suppress=False)
        except Exception:
            pass

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

    def _build_and_show(self, x: int, y: int, keep_panel: bool = False):
        # Rebuild: close old windows but keep the session (paste target).
        # keep_panel=True only on _refresh — a fresh show() closes any
        # stale panel from the previous position.
        self._close_windows(keep_panel=keep_panel)

        # Theme + opacity + icon pack from settings
        theme = self.history.settings.get("theme", "dark") if self.history else "dark"
        self._colours = DARK if theme == "dark" else LIGHT
        self._opacity = self.history.settings.get("transparency", 1.0) if self.history else 1.0
        if self.history:
            set_icon_pack(self.history.settings.get("icon_pack", "default"))
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
        # Translucent window + inner rounded "card" + Qt drop shadow =
        # modern elevation. This is the standard frameless-depth recipe:
        # DWM shadows don't render on layered (translucent) windows on
        # Win10, so the shadow is painted by Qt into transparent margins.
        popup.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground)
        popup.setWindowOpacity(self._opacity)
        self._popup = popup

        # WS_EX_NOACTIVATE is applied after show() via QTimer (winId only valid post-show).
        # NOTE: popup.show() is intentionally called AFTER the layout is fully built
        # and positioned — see the bottom of this method. Do NOT move it up here.

        # INVARIANT: shadow blur + |offset| MUST fit inside these margins.
        # The effect's repaint region extends the card by ~blurRadius; if
        # that overflows the window rect, Windows rejects the layered-
        # window update outright (UpdateLayeredWindowIndirect "parameter
        # is incorrect") and the popup freezes showing stale content.
        outer = QVBoxLayout(popup)
        outer.setContentsMargins(18, 14, 18, 22)
        card = QWidget(popup)
        card.setObjectName("clipdrop_card")
        card.setStyleSheet(
            f"QWidget#clipdrop_card {{background:{C['bg']};"
            f"border:1px solid {C['border']};border-radius:10px;}}")
        _shadow = QGraphicsDropShadowEffect(card)
        _shadow.setBlurRadius(15)     # 15 + offset 3 < margins (18/14/22)
        _shadow.setOffset(0, 3)
        _shadow.setColor(QColor(0, 0, 0, 150))
        card.setGraphicsEffect(_shadow)
        outer.addWidget(card)

        main_lay = QVBoxLayout(card)
        main_lay.setContentsMargins(1, 1, 1, 9)   # bottom pad = rounded base
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
        # Explicit dark background — the card's stylesheet is selector-
        # scoped and no longer cascades here (was the white-rows bug).
        self._list_container.setStyleSheet(f"background:{C['bg']};")
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
                             + _scrollbar_qss(C))
        scroll.setFixedWidth(POPUP_WIDTH + 10)
        max_h = min(len(items) * ITEM_HEIGHT + 4, 480) if items else 100
        scroll.setFixedHeight(max_h)
        main_lay.addWidget(scroll)
        self._scroll = scroll   # kept so _refresh can resize in place
        # Chrome height = everything around the scroll area (header, search
        # bar, separators, margins). Measured HERE, where the fresh layout
        # is known-correct — _refresh derives exact window heights from it
        # instead of trusting sizeHint(), which can be stale mid-mutation
        # and leaves the window too tall (content then spreads with gaps).
        self._chrome_h = None   # set right after adjustSize() below

        # Connect search
        self._search_edit.textChanged.connect(self._on_search)

        # Escape is handled by the global keyboard hook (see __init__) —
        # a QShortcut would only fire while the window is active, and
        # this window deliberately never activates.

        # Build is complete — now size, position, THEN show.
        # Showing AFTER positioning means the window appears exactly where
        # it should on the first paint — no flash at 0,0 first.
        popup.adjustSize()
        self._chrome_h = popup.height() - max_h   # see note at _scroll above
        self._position_popup(x, y)
        popup.show()
        # WS_EX_NOACTIVATE — winId is valid now that show() has been called.
        QTimer.singleShot(0, lambda: _set_no_activate(int(popup.winId())))
        popup.raise_()
        # "Hover to close" mode (settings): poll the cursor while open
        self._start_hover_close_if_enabled()

    def _build_header(self, parent, items, C) -> QWidget:
        hdr = QWidget(parent)
        hdr.setFixedHeight(36)
        # Gradient surface (lighter top → darker base) + a dark seam at
        # the bottom edge = raised 3D header. Top radii follow the card.
        hdr.setStyleSheet(
            f"background:{_grad_v(C['accent_light'], _shade(C['accent'], -0.18))};"
            f"border-top-left-radius:9px;"
            f"border-top-right-radius:9px;"
            f"border-bottom:1px solid rgba(0,0,0,90);")

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

        # Item count — doubles as the "clear selection" button when a
        # Ctrl+click multi-selection is active ("✕ N selected")
        count_lbl = QLabel(f"{len(items)} items", hdr)
        count_lbl.setFont(QFont("Segoe UI", 8))
        count_lbl.setStyleSheet("color:#c7d2fe;background:transparent;")
        count_lbl.mousePressEvent = lambda e: self._clear_selection()
        lay.addWidget(count_lbl)
        self._count_lbl = count_lbl
        if self._selected_ids:          # restore "N selected" after rebuilds
            self._update_count_label()

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
        # FIXED height — without it the bar is the only stretchable child
        # and absorbs all leftover space when the list shrinks (switching
        # to a profile with few items made it fill half the window).
        bar.setFixedHeight(34)
        # Inset "channel" look: darker recessed field, shadow line above,
        # faint highlight below — reads as pressed-into the surface.
        bar.setStyleSheet(
            f"background:{_shade(C['bg_item'], -0.25)};"
            f"border-top:1px solid rgba(0,0,0,80);"
            f"border-bottom:1px solid rgba(255,255,255,14);")
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
        # The popup is WS_EX_NOACTIVATE (never takes keyboard focus) so
        # paste lands in the target app. That also blocks typing here —
        # so clicking INTO the search box activates the window on demand.
        # The paste worker re-foregrounds the target before Ctrl+V.
        _orig_press = edit.mousePressEvent
        def _press(e):
            self._activate_for_search(edit)
            _orig_press(e)
        edit.mousePressEvent = _press
        lay.addWidget(edit)

        clear = QLabel("✕", bar)
        clear.setFont(QFont("Segoe UI", 9))
        clear.setStyleSheet(f"color:{C['text_dim']};background:transparent;")
        clear.setCursor(Qt.CursorShape.PointingHandCursor)
        clear.mousePressEvent = lambda e: edit.clear()
        lay.addWidget(clear)

        return bar, edit

    def _activate_for_search(self, edit):
        """Strip WS_EX_NOACTIVATE and activate the popup so the search box
        can receive keystrokes. Only happens when the user clicks into the
        search field — list clicks never activate, so normal paste flow
        keeps the target app focused. The paste target hwnd is already
        saved (_paste_target), and the paste worker restores its focus
        before sending Ctrl+V."""
        popup = self._popup
        if not popup:
            return
        try:
            hwnd = int(popup.winId())
            ex = win32gui.GetWindowLong(hwnd, win32con.GWL_EXSTYLE)
            if ex & win32con.WS_EX_NOACTIVATE:
                win32gui.SetWindowLong(hwnd, win32con.GWL_EXSTYLE,
                                       ex & ~win32con.WS_EX_NOACTIVATE)
            win32gui.SetForegroundWindow(hwnd)
        except Exception:
            pass
        popup.activateWindow()
        edit.setFocus(Qt.FocusReason.MouseFocusReason)

    def _build_empty_label(self, parent, C):
        lbl = QLabel("No clipboard history yet.\nCopy something to get started!", parent)
        lbl.setAlignment(Qt.AlignmentFlag.AlignCenter)
        lbl.setFont(QFont("Segoe UI", 10))
        lbl.setStyleSheet(f"color:{C['text_dim']};background:{C['bg']};padding:24px;")
        self._list_lay.addWidget(lbl)

    def _populate_list(self, items: list):
        C = self._colours
        # Clear existing rows. hide() BEFORE deleteLater: removed widgets
        # stay parented (and paintable) until the deferred delete runs —
        # visible ghosts of the old profile otherwise.
        while self._list_lay.count():
            child = self._list_lay.takeAt(0)
            w = child.widget()
            if w is not None:
                w.hide()
                w.deleteLater()

        for item in items:
            row = ItemRowWidget(item, self.history, self.profiles, C, self._list_container)
            row.sig_paste.connect(self._paste_item)
            row.sig_pin.connect(self._toggle_pin)
            row.sig_delete.connect(self._delete_item)
            row.sig_move_up.connect(self._move_up)
            row.sig_move_dn.connect(self._move_down)
            row.sig_rclick.connect(self._show_send_to_menu)
            row.sig_select.connect(self._toggle_select)
            row.sig_drag.connect(self._start_drag)
            if item["id"] in self._selected_ids:
                row.set_selected(True)   # selection survives list rebuilds

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

        def paste_single_file(fps):
            # Accepts one path or a list — a click on a multi-selected
            # row pastes every selected file as ONE clipboard payload.
            if isinstance(fps, str):
                fps = [fps]
            if not fps:
                return
            file_item = {
                "id":      hashlib.md5("|".join(fps).encode()).hexdigest(),
                "type":    "file",
                "content": list(fps),
                "source":  os.path.dirname(fps[0]),
            }
            # Route through _paste_item: hides popup + side panel, then
            # runs the paste on the worker thread (never blocks the UI).
            self._paste_item(file_item)

        panel = SidePanelWidget(files, item, self.history, self._colours,
                                paste_single_file, self._popup,
                                controller=self)
        self._side_panel = panel

        # Smart positioning: open on whichever side of the popup has room.
        # Prefer the right (natural flyout direction); fall back to the
        # left when the popup sits near the right screen edge; if neither
        # side fully fits, use whichever has more space, clamped on-screen.
        if self._popup:
            pw, ph = panel.width(), panel.height()
            pop    = self._popup.geometry()
            screen = (QApplication.screenAt(pop.center())
                      or QApplication.primaryScreen())
            g = screen.availableGeometry()

            space_right = g.right() - pop.right()
            space_left  = pop.left() - g.left()

            # Both windows carry transparent shadow margins (popup 18px,
            # panel 14px) — overlap the frames so the visible cards sit
            # ~2px apart AND the cursor never crosses a dead zone between
            # windows (transparent pixels are click-through, so overlap
            # is harmless).
            if space_right >= pw or space_right >= space_left:
                px = pop.right() - 30           # flyout to the right
            else:
                px = pop.left() - pw + 30       # flyout to the left
            px = max(g.left(), min(px, g.right() - pw))

            # Align with the hovered row, clamped so the panel stays on-screen
            py = pop.y() + row.y()
            py = max(g.top(), min(py, g.bottom() - ph))

            panel.move(px, py)
        panel.show()

    # ── Position ──────────────────────────────────────────────────────────────

    def _position_popup(self, x: int, y: int):
        popup = self._popup
        popup.adjustSize()
        w = popup.width()
        h = popup.height()
        # Use the monitor the cursor is actually on — primaryScreen() is
        # wrong on multi-monitor setups where a secondary screen sits at
        # negative coordinates or to the right of the primary.
        # availableGeometry() excludes the taskbar so the popup never
        # opens underneath it.
        screen = QApplication.screenAt(QPoint(x, y)) or QApplication.primaryScreen()
        g = screen.availableGeometry()
        px = x if x + w <= g.right() else g.right() - w - 4
        px = max(g.left(), px)
        py = y if y + h <= g.bottom() else y - h
        py = max(g.top(), py)
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
        if not self.profiles or not self._popup:
            return
        # Parent to the popup: if the popup closes, the menu dies with it
        # instead of surviving as a stuck orphan on screen.
        menu = QMenu(self._popup)
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
        _activate_for_menu(self._popup)   # menu needs an ACTIVE owner to grab
        chosen = menu.exec(btn.mapToGlobal(QPoint(0, btn.height())))
        if chosen:
            self.profiles.set_active(chosen.data())
            self._refresh()

    def _show_send_to_menu(self, item: dict, gpos: QPoint):
        if not self.profiles or not self._popup:
            return
        menu = QMenu(self._popup)   # dies with the popup — never orphaned
        menu.setStyleSheet(f"""
            QMenu {{ background:{self._colours['bg_item']}; color:{self._colours['text']};
                     border:1px solid {self._colours['border']}; font-family:'Segoe UI'; }}
            QMenu::item:selected {{ background:{self._colours['bg_hover']}; }}
        """)
        menu.addAction("Send to profile…").setEnabled(False)
        menu.addSeparator()
        # Every profile EXCEPT the one currently shown (sending an item to
        # the profile you're looking at is a no-op). General included.
        active_id = self.profiles.get_active_profile()["id"]
        for prof in self.profiles.get_all_profiles():
            if prof["id"] == active_id:
                continue
            act = menu.addAction(prof["name"])
            act.setData(prof["id"])
        _activate_for_menu(self._popup)   # menu needs an ACTIVE owner to grab
        chosen = menu.exec(gpos)
        if chosen and chosen.data():
            self._send_item_to_profile(item, chosen.data(), chosen.text())

    def _send_item_to_profile(self, item: dict, profile_id: str, profile_name: str):
        """Send a history item to a profile. 'General' is special: it is
        simply the un-hidden history list, so sending there means clearing
        the item's hidden flag (set when side-panel files become their own
        entries)."""
        if profile_id == "general":
            entry = self.history._find_by_id(item["id"])
            if entry is not None and entry.get("hidden"):
                entry["hidden"] = False
                self.history._save_history()
        else:
            self.profiles.add_item_to_profile(item["id"], profile_id)
        self._show_toast(f'Sent to "{profile_name}"')
        self._refresh()

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

    def _refresh(self, full: bool = False):
        """Update the OPEN popup live — like the side panels do.

        Default (light) refresh rebuilds only the row list and header
        labels inside the existing window: no destroy/recreate, no
        flicker. This is the same machinery live search filtering uses.

        full=True tears the window down and rebuilds it — needed only
        when the window CHROME changes (theme switch restyles the card,
        header gradient, scrollbars…). Used by the settings panel.
        """
        if not self._popup:
            return
        if full:
            self._build_and_show(self._popup.x(), self._popup.y(),
                                 keep_panel=True)
            return

        # Re-fetch data
        if self.profiles:
            items = self.profiles.get_active_items()
        else:
            items = self.history.get_all() if self.history else []
        self._items_all = items

        # Mutate with painting SUSPENDED, then repaint the WHOLE window
        # once. Resizing a visible translucent (layered) window while
        # partial dirty regions are pending makes Windows reject the
        # update entirely (UpdateLayeredWindowIndirect: "parameter is
        # incorrect", dirty rect from the OLD size) — the popup then
        # freezes showing the previous profile. A single full-rect
        # repaint after the resize can never mismatch.
        popup = self._popup
        popup.setUpdatesEnabled(False)
        try:
            # Rows — respect an active search filter if one is typed
            query = self._search_edit.text() if self._search_edit else ""
            if query.strip():
                self._on_search(query)     # repopulates + sets count label
            else:
                self._populate_list(items)
                if not items:
                    self._build_empty_label(self._list_container, self._colours)
                if self._count_lbl:
                    self._count_lbl.setText(f"{len(items)} items")

            # Header profile name (active profile may have changed)
            if getattr(self, "_prof_btn", None) is not None and self.profiles:
                try:
                    name = self.profiles.get_active_profile()["name"]
                    self._prof_btn.setText(f"{name}  ▾")
                except RuntimeError:
                    pass

            # Window height follows the item count — computed EXACTLY from
            # the chrome height measured at build time and hard-set.
            # (sizeHint-based resizing proved unreliable mid-mutation: a
            # stale hint left the window tall and the fixed-height children
            # spread apart with exposed gaps.)
            if getattr(self, "_scroll", None) is not None:
                max_h = min(len(items) * ITEM_HEIGHT + 4, 480) if items else 100
                self._scroll.setFixedHeight(max_h)
                chrome = getattr(self, "_chrome_h", None)
                if chrome:
                    popup.setFixedHeight(chrome + max_h)
                else:   # fallback — should not happen after a normal build
                    lay = popup.layout()
                    if lay is not None:
                        lay.activate()
                    popup.adjustSize()
        finally:
            popup.setUpdatesEnabled(True)
            popup.update()
            # One more full repaint AFTER the deferred row deletions run
            def _late_update():
                try:
                    if popup.isVisible():
                        popup.update()
                except RuntimeError:
                    pass
            QTimer.singleShot(0, _late_update)

        # Close-behaviour setting may have changed
        self._start_hover_close_if_enabled()

    # ── Multi-selection + drag-out ───────────────────────────────────────────

    def _toggle_select(self, item: dict, row):
        """Ctrl+click: toggle an item in/out of the multi-selection."""
        iid = item["id"]
        if iid in self._selected_ids:
            self._selected_ids.discard(iid)
            row.set_selected(False)
        else:
            self._selected_ids.add(iid)
            row.set_selected(True)
        self._update_count_label()

    def _clear_selection(self):
        """Deselect everything (header ✕ badge, or first Escape press)."""
        if not self._selected_ids:
            return
        self._selected_ids.clear()
        if self._list_container is not None:
            try:
                for r in self._list_container.findChildren(ItemRowWidget):
                    if r._selected:
                        r.set_selected(False)
            except RuntimeError:
                pass
        self._update_count_label()

    def _update_count_label(self):
        lbl = self._count_lbl
        if lbl is None:
            return
        try:
            n = len(self._selected_ids)
            if n:
                lbl.setText(f"✕  {n} selected")
                lbl.setStyleSheet("color:#ffffff;background:transparent;"
                                  "font-weight:bold;")
                lbl.setCursor(Qt.CursorShape.PointingHandCursor)
                lbl.setToolTip("Clear selection")
            else:
                lbl.setText(f"{len(getattr(self, '_items_all', []) or [])} items")
                lbl.setStyleSheet("color:#c7d2fe;background:transparent;")
                lbl.setCursor(Qt.CursorShape.ArrowCursor)
                lbl.setToolTip("")
        except RuntimeError:
            pass   # label already destroyed with an old window

    def _on_escape(self):
        """Escape steps back: side-panel selection → main selection →
        close the popup. Only acts while the popup is open."""
        if not self._popup or not self._popup.isVisible():
            return
        panel = self._side_panel
        if panel is not None:
            try:
                if panel.isVisible() and panel._list.selectedItems():
                    panel._list.clearSelection()
                    return
            except RuntimeError:
                pass
        if self._selected_ids:
            self._clear_selection()
        else:
            self.hide()

    def _combined_selection_item(self) -> dict | None:
        """Merge the multi-selection into ONE pasteable item.

        All text kinds  → texts joined with newlines (single Ctrl+V).
        All files/images→ one multi-file entry (images by their PNG path).
        Mixed           → None; the clipboard can't hold both sensibly.
        Selection order follows the visible list order.
        """
        sel = [it for it in self._items_all if it["id"] in self._selected_ids]
        if not sel:
            return None
        texts = [it for it in sel if it.get("type") in _TEXT_KINDS]
        paths = []
        for it in sel:
            if it.get("type") == "file" and isinstance(it.get("content"), list):
                paths.extend(it["content"])
            elif it.get("type") == "image":
                paths.append(str(it["content"]))
        if texts and not paths:
            return {"id": "multi-sel", "type": "text",
                    "content": "\n".join(str(t["content"]) for t in texts),
                    "source": f"{len(texts)} selected items"}
        if paths and not texts:
            return {"id": "multi-sel", "type": "file",
                    "content": paths,
                    "source": f"{len(sel)} selected items"}
        return None   # mixed text + files

    def _drag_payload(self, item: dict) -> list:
        """Items a drag from this row carries: the whole selection when
        the row is part of it, otherwise just the row itself."""
        if item["id"] in self._selected_ids:
            return [it for it in self._items_all
                    if it["id"] in self._selected_ids]
        return [item]

    def _start_drag(self, item: dict, row):
        """Drag rows OUT of ClipDrop — drop into any app to paste there.
        Runs synchronously from the row's mouse-move (Qt's DnD pattern);
        the popup stays open and never takes focus, so the drop target
        receives the data exactly like an Explorer drag."""
        items = self._drag_payload(item)
        drag  = QDrag(row)
        drag.setMimeData(_mime_for_items(items))

        # Drag pixmap: the grabbed row, with a count bubble when multiple
        pm = row.grab()
        if pm.width() > 260:
            pm = pm.scaledToWidth(260, Qt.TransformationMode.SmoothTransformation)
        if len(items) > 1:
            p = QPainter(pm)
            p.setRenderHint(QPainter.RenderHint.Antialiasing)
            p.setBrush(QBrush(QColor(self._colours["accent"])))
            p.setPen(Qt.PenStyle.NoPen)
            p.drawEllipse(pm.width()-30, 4, 24, 24)
            p.setPen(QPen(QColor("white")))
            f = p.font(); f.setBold(True); p.setFont(f)
            p.drawText(QRect(pm.width()-30, 4, 24, 24),
                       Qt.AlignmentFlag.AlignCenter, str(len(items)))
            p.end()
        drag.setPixmap(pm)
        drag.setHotSpot(QPoint(pm.width() // 3, pm.height() // 2))

        # Text-only payloads allow MOVE and DEFAULT to it — edit controls
        # propose Move for dropped text and some reject anything else.
        # (Moving costs nothing: the history item is never deleted.)
        # Anything carrying file URLs stays Copy-only: a Move-accepting
        # target would relocate the user's actual files on disk.
        mime = drag.mimeData()
        if mime.hasUrls():
            actions, default = (Qt.DropAction.CopyAction,
                                Qt.DropAction.CopyAction)
        else:
            actions = Qt.DropAction.CopyAction | Qt.DropAction.MoveAction
            default = Qt.DropAction.MoveAction

        _DRAG_STATE["active"] = True
        try:
            drag.exec(actions, default)
        finally:
            _DRAG_STATE["active"] = False
            # The release event is consumed by the drag — reset by hand
            try:
                row._press_pos    = None
                row._is_dragging  = False
                row._drag_started = False
            except RuntimeError:
                pass   # row deleted by a refresh during the drag

    # ── Hide ──────────────────────────────────────────────────────────────────

    def _close_windows(self, keep_panel: bool = False):
        """Close the popup + side panel widgets. Used both by a real hide
        and by _build_and_show's rebuild — does NOT end the popup session.

        keep_panel=True (refresh path) leaves the side panel open so
        per-file actions (pin/send/delete) can refresh the main list
        without yanking the panel out from under the user.
        """
        if self._side_panel and not keep_panel:
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

    def _do_hide(self):
        self._close_windows()
        if self._hover_timer:
            self._hover_timer.stop()
        self._selected_ids.clear()   # selection is per popup session
        # Popup session over — forget the paste target so the next show()
        # captures the then-foreground window, not a stale one. (_refresh
        # rebuilds must NOT do this — they keep the session alive, which
        # is why the window-closing above is a separate method.)
        self._paste_target = None

    # ── Hover-to-close mode ───────────────────────────────────────────────────

    def _start_hover_close_if_enabled(self):
        """Settings 'close_mode' == 'hover': the popup closes as soon as
        the cursor moves outside it. A 350 ms cursor poll is used instead
        of leave-events — it naturally covers the side panels, nested
        folder panels and QMenus without per-window event plumbing."""
        mode = (self.history.settings.get("close_mode", "click")
                if self.history else "click")
        if self._hover_timer is None:
            self._hover_timer = QTimer(self)
            self._hover_timer.timeout.connect(self._hover_close_check)
        if mode == "hover":
            self._hover_seen_inside = False
            self._hover_timer.start(350)
        else:
            self._hover_timer.stop()

    def _hover_close_check(self):
        win = self._popup
        if not win or not win.isVisible():
            self._hover_timer.stop()
            return
        if _DRAG_STATE["active"]:
            return   # never close the popup out from under an active drag
        # A context menu is open — its cursor position is "outside" the
        # popup but the user is mid-interaction. Never close under a menu.
        if QApplication.activePopupWidget() is not None:
            return
        # The user is typing in the search box — closing while they type
        # would be hostile. Pause while the search edit holds focus.
        edit = getattr(self, "_search_edit", None)
        if edit is not None:
            try:
                if edit.hasFocus():
                    return
            except RuntimeError:
                pass   # search edit's C++ side already deleted
        gp = QCursor.pos()
        if win.frameGeometry().contains(gp):
            self._hover_seen_inside = True
            return
        p = self._side_panel
        while p is not None:                # popup → panel → nested panel
            try:
                if p.isVisible() and p.frameGeometry().contains(gp):
                    self._hover_seen_inside = True
                    return
                p = p._sub_panel
            except RuntimeError:
                break
        # Cursor is outside everything. Only close if it was inside at
        # least once — the popup can open clamped away from the cursor,
        # and closing before the user ever reaches it would be a misfire.
        if self._hover_seen_inside:
            self.hide()

    # ── Paste ─────────────────────────────────────────────────────────────────

    def _paste_item(self, item: dict):
        """Run the paste sequence on a worker thread. The popup STAYS OPEN.

        WS_EX_NOACTIVATE means the popup never holds keyboard focus, so
        the target app keeps focus the whole time and Ctrl+V lands there
        even while the popup is visible. The user can paste several items
        in a row; the popup only closes on outside click or Escape.

        The main thread only spawns the worker — it never sleeps, so all
        UI stays responsive throughout the paste.
        """
        # Ignore clicks while a paste is already in flight
        if self._paste_worker and self._paste_worker.isRunning():
            return
        # Clicking a row that's part of a multi-selection pastes the WHOLE
        # selection as one combined payload.
        if item["id"] in self._selected_ids and len(self._selected_ids) > 1:
            combined = self._combined_selection_item()
            if combined is None:
                self._show_toast("⚠ Mixed selection — can't paste text and "
                                 "files together")
                return
            item = combined
        # Item type vs paste target: pasting raw text/code into File
        # Explorer or the desktop does nothing — tell the user instead of
        # failing silently.
        target  = getattr(self, "_paste_target", None)
        blocked = self._paste_blocked_reason(item, target)
        if blocked:
            self._show_toast(blocked)
            return
        # Image → Explorer/desktop: image items are backed by a real PNG
        # on disk, so paste them there as a FILE copy (CF_HDROP) — raw
        # bitmap data (CF_DIB) would be a no-op in a folder view.
        if (item.get("type") == "image"
                and self._target_class(target) in self._FILE_ONLY_TARGETS):
            item = {**item, "type": "file", "content": [item["content"]]}
        # Close only the transient hover side panel, not the popup.
        if self._side_panel:
            try:
                self._side_panel.close()
            except Exception:
                pass
            self._side_panel = None

        target = getattr(self, "_paste_target", None)

        worker = _PasteWorker(item, self.watcher, target, parent=self)
        worker.failed.connect(self._on_paste_failed)
        worker.finished.connect(self._on_paste_finished)
        self._paste_worker = worker   # keep reference — prevents GC mid-run
        worker.start()
        self._show_toast(f"Paste  {self._paste_label(item)}")

    # Window classes whose paste area only accepts FILES — Ctrl+V of raw
    # text is a silent no-op there. (Images are fine: they get converted
    # to a file paste of their saved PNG — see _paste_item.)
    _FILE_ONLY_TARGETS = {"CabinetWClass", "ExploreWClass",   # File Explorer
                          "Progman", "WorkerW"}               # Desktop

    def _target_class(self, target) -> str:
        if not target:
            return ""
        try:
            return win32gui.GetClassName(target)
        except Exception:
            return ""   # can't identify the target

    def _paste_blocked_reason(self, item: dict, target):
        """Error string if this item TYPE cannot be pasted into the target
        window (raw text into File Explorer / desktop), else None."""
        if (self._target_class(target) in self._FILE_ONLY_TARGETS
                and item.get("type") not in ("file", "image")):
            return "⚠ Cannot paste text here"
        return None

    def _paste_label(self, item: dict) -> str:
        """Short human label for the paste notification."""
        t = item.get("type", "")
        if t == "file":
            c = item.get("content") or []
            if len(c) == 1:
                return os.path.basename(c[0])
            return f"{len(c)} files"
        if t == "image":
            return "image"
        prev = self.history.get_preview(item) if self.history else str(item.get("content", ""))
        prev = " ".join(str(prev).split())          # collapse whitespace
        return prev[:40] + "…" if len(prev) > 40 else prev

    def _on_paste_failed(self, msg: str):
        print(f"[ClipDrop] Paste error: {msg}")
        self._show_toast("Paste failed")

    def _on_paste_finished(self):
        if self._paste_worker:
            self._paste_worker.deleteLater()
            self._paste_worker = None


    # ── Toast ────────────────────────────────────────────────────────────────

    def _show_toast(self, msg: str, duration: int = 1500):
        """In-app toast near the popup, gone within 1.5 seconds.

        Replaces the old tray-balloon notification, which rendered as a
        heavy bold Windows toast and lingered for several seconds.
        """
        try:
            toast = ToastWidget(msg, self._popup, duration=duration)
            # Keep a reference so the toast isn't GC'd mid-display;
            # WA_DeleteOnClose fires destroyed → cleanup.
            if not hasattr(self, "_toasts"):
                self._toasts = []
            self._toasts.append(toast)
            toast.destroyed.connect(
                lambda *_: self._toasts.remove(toast)
                if toast in self._toasts else None)
        except Exception:
            pass
