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
    QGraphicsOpacityEffect, QGraphicsDropShadowEffect, QStyledItemDelegate,
)
from PyQt6.QtCore import (
    Qt, QTimer, QPoint, QSize, QRect, QRectF, QPointF, QPropertyAnimation,
    QVariantAnimation, QEasingCurve, pyqtSignal, QObject, pyqtSlot,
    QThread, QEvent,
)
from PyQt6.QtGui import (
    QColor, QPainter, QPen, QBrush, QFont, QFontMetrics,
    QPixmap, QImage, QCursor, QIcon, QPalette, QPolygonF,
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
    "hex":    "#ec4899",
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
for _e in ['.py','.js','.ts','.jsx','.tsx','.java','.c','.cpp','.h','.cs',
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
        f"QScrollBar:vertical {{background:transparent;width:10px;"
        f"margin:2px 2px 2px 0;border:none;}}"
        f"QScrollBar::handle:vertical {{"
        f"background:qlineargradient(x1:0,y1:0,x2:1,y2:0,"
        f"stop:0 {handle_top},stop:1 {handle_bot});"
        f"border-radius:4px;min-height:28px;}}"
        f"QScrollBar::handle:vertical:hover {{background:{hover};}}"
        f"QScrollBar::handle:vertical:pressed {{background:{C['accent_light']};}}"
        f"QScrollBar::add-line:vertical,QScrollBar::sub-line:vertical {{height:0;}}"
        f"QScrollBar::add-page:vertical,QScrollBar::sub-page:vertical "
        f"{{background:none;}}")

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


def _icon_pixmap(icon_type: str, size: int = 32, colour_hint: str = None) -> QPixmap:
    """Crash-proof, cached icon factory.

    The hand-drawn icons below use fixed pixel coordinates tuned for
    size=32; at smaller sizes some shapes can invert (x1 < x0) and PIL
    raises ValueError. In PyQt6 an unhandled exception in a slot aborts
    the entire app — a decorative icon must never be able to do that,
    so any drawing error falls back to a plain colour badge.

    colour_hint: for "hex" icons — the actual colour code the swatch shows.
    """
    key = (icon_type, size, colour_hint)
    if key in _ICON_CACHE:
        return _ICON_CACHE[key]
    try:
        pm = _draw_icon_pixmap(icon_type, size, colour_hint)
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


def _draw_icon_pixmap(icon_type: str, size: int = 32,
                      colour_hint: str = None) -> QPixmap:
    """Return a QPixmap for the given icon type, using PIL to draw it.
    Rasters at _SS× resolution and downscales with LANCZOS for crispness;
    branch code below works in logical `size` coordinates throughout."""
    from PIL import ImageDraw
    img = Image.new("RGBA", (size * _SS, size * _SS), (0, 0, 0, 0))
    d   = _ScaledDraw(ImageDraw.Draw(img), _SS)

    if icon_type == "hex":
        # Hex colour code — a swatch of the ACTUAL colour with a "#".
        col = (colour_hint or "").strip()
        if len(col) in (4, 5):    # #RGB / #RGBA → expand to #RRGGBB
            col = "#" + "".join(ch * 2 for ch in col[1:4])
        elif len(col) == 9:       # #RRGGBBAA → drop alpha
            col = col[:7]
        try:
            r, g, b = (int(col[i:i+2], 16) for i in (1, 3, 5))
        except (ValueError, IndexError):
            r, g, b = 236, 72, 153   # generic pink swatch if unparsable
            col = "#ec4899"
        d.rounded_rectangle([1, 1, size-1, size-1], radius=size*0.16, fill=col)
        d.rounded_rectangle([1, 1, size-1, size-1], radius=size*0.16,
                            outline="#00000040", width=1)
        # '#' glyph in black or white — whichever contrasts with the colour
        lum = 0.299*r + 0.587*g + 0.114*b
        fg  = "#1e1e1e" if lum > 140 else "white"
        f = _bold_font(max(6, int(size*0.55)))
        if f:
            d.text((size/2, size*0.52), "#", font=f, fill=fg, anchor="mm")
        img = img.resize((size, size), Image.LANCZOS)
        data = img.tobytes("raw", "RGBA")
        qimg = QImage(data, size, size, QImage.Format.Format_RGBA8888)
        return QPixmap.fromImage(qimg)

    if icon_type == "text":
        # Clipboard TEXT — copied CHARACTERS, not a file. Font symbol 🗚:
        # big "A" + small "a". The .txt FILE icon is "txt" below — a
        # paper sheet. Do not confuse the two.
        d.rounded_rectangle([1,1,size-1,size-1], radius=5, fill="#4f46e5")
        f_big   = _bold_font(max(6, int(size*0.62)))
        f_small = _bold_font(max(5, int(size*0.38)))
        if f_big and f_small:
            d.text((size*0.40, size*0.50), "A", font=f_big,   fill="white", anchor="mm")
            d.text((size*0.78, size*0.62), "a", font=f_small, fill="white", anchor="mm")
        else:   # no TTF available — hand-drawn "A"
            k = size / 32
            d.line([16*k, 6*k, 8*k,  26*k], fill="white", width=max(1,int(3*k)))
            d.line([16*k, 6*k, 24*k, 26*k], fill="white", width=max(1,int(3*k)))
            d.line([11*k, 19*k, 21*k, 19*k], fill="white", width=max(1,int(3*k)))
    elif icon_type == "txt":
        # Text FILE (.txt/.rtf/…) — paper with stripes 📝
        k    = size / 32
        fold = max(2, int(7*k))
        L, T = int(5*k), int(2*k)
        R, B = size-int(5*k), size-int(2*k)
        d.polygon([(L,T),(R-fold,T),(R,T+fold),(R,B),(L,B)], fill="#f8fafc")
        d.polygon([(R-fold,T),(R,T+fold),(R-fold,T+fold)], fill="#cbd5e1")
        x0, x1 = int(9*k), size-int(9*k)
        lh = max(1, int(2*k))
        for i in range(4):
            y = int((10+5*i)*k)
            d.rectangle([x0, y, x1, y+lh], fill="#64748b")
    elif icon_type == "url":
        # URL / web link — chain-link symbol 🔗: two interlocking rounded
        # links drawn upright on a transparent layer, rotated 45°, then
        # composited onto the tile (PIL can't rotate primitives directly).
        k = size / 32
        d.rounded_rectangle([1,1,size-1,size-1], radius=6*k, fill="#0ea5e9")
        layer = Image.new("RGBA", (size * _SS, size * _SS), (0, 0, 0, 0))
        ld = _ScaledDraw(ImageDraw.Draw(layer), _SS)
        lw = max(2, int(3*k))
        w2 = max(2, int(5*k))          # narrow links → elongated capsules
        cx = size // 2
        ld.rounded_rectangle([cx-w2, int(2*k),  cx+w2, int(17*k)],
                             radius=w2, outline="white", width=lw)
        ld.rounded_rectangle([cx-w2, int(13*k), cx+w2, int(28*k)],
                             radius=w2, outline="white", width=lw)
        layer = layer.rotate(45, resample=Image.BICUBIC,
                             center=(size * _SS / 2, size * _SS / 2))
        img.alpha_composite(layer)
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
        # Office-style tile: Excel green, white bold "X"
        d.rounded_rectangle([1,1,size-1,size-1], radius=int(size*0.16), fill="#107C41")
        f = _bold_font(max(6, int(size*0.62)))
        if f:
            d.text((size/2, size*0.52), "X", font=f, fill="white", anchor="mm")
        else:
            d.line([6,8,size-6,size-6], fill="white", width=3)
            d.line([size-6,8,6,size-6], fill="white", width=3)
    elif icon_type == "word":
        # Office-style tile: Word blue, white bold "W"
        d.rounded_rectangle([1,1,size-1,size-1], radius=int(size*0.16), fill="#185ABD")
        f = _bold_font(max(6, int(size*0.58)))
        if f:
            d.text((size/2, size*0.52), "W", font=f, fill="white", anchor="mm")
        else:
            for i,x2 in enumerate([size-5,size-8,size-12]):
                if x2 > 4:
                    d.rectangle([4,8+i*6,x2,10+i*6], fill="white")
    elif icon_type == "ppt":
        # Office-style tile: PowerPoint orange-red, white bold "P"
        d.rounded_rectangle([1,1,size-1,size-1], radius=int(size*0.16), fill="#C43E1C")
        f = _bold_font(max(6, int(size*0.62)))
        if f:
            d.text((size/2, size*0.52), "P", font=f, fill="white", anchor="mm")
        else:
            d.ellipse([5,5,size-5,size-5], fill="#fbbf24")
    elif icon_type == "pdf":
        # Red tile with white "PDF" lettering
        d.rounded_rectangle([1,1,size-1,size-1], radius=int(size*0.16), fill="#dc2626")
        f = _bold_font(max(5, int(size*0.30)))
        if f:
            d.text((size/2, size*0.52), "PDF", font=f, fill="white", anchor="mm")
        else:
            for i in range(3):
                d.rectangle([6,10+i*6,size-6,11+i*6], fill="white")
    elif icon_type == "dll":
        # Library file — gear symbol ⚙ on a slate tile (k-scaled so it
        # renders correctly at every size, unlike the fixed-coord exe gear)
        import math
        k = size / 32
        d.rounded_rectangle([1,1,size-1,size-1], radius=5*k, fill="#475569")
        cx = cy = size / 2
        Ro, Ri, Rh = 13*k, 10*k, 4*k
        d.ellipse([cx-Ro,cy-Ro,cx+Ro,cy+Ro], fill="white")
        d.ellipse([cx-Ri,cy-Ri,cx+Ri,cy+Ri], fill="#475569")
        for deg in range(0, 360, 45):
            a  = math.radians(deg)
            tx = cx + (Ro-k)*math.cos(a)
            ty = cy + (Ro-k)*math.sin(a)
            r3 = 3*k
            d.ellipse([tx-r3,ty-r3,tx+r3,ty+r3], fill="white")
        d.ellipse([cx-Ri+k,cy-Ri+k,cx+Ri-k,cy+Ri-k], fill="white")
        d.ellipse([cx-Rh,cy-Rh,cx+Rh,cy+Rh], fill="#475569")
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
        # HTML — globe symbol 🌐: sphere with meridians and parallels
        k  = size / 32
        cx = cy = size / 2
        r  = size/2 - 2*k
        lw = max(1, int(2*k))
        d.ellipse([cx-r, cy-r, cx+r, cy+r], fill="#0ea5e9")
        d.ellipse([cx-r, cy-r, cx+r, cy+r], outline="white", width=lw)
        d.ellipse([cx-r*0.45, cy-r, cx+r*0.45, cy+r], outline="white", width=lw)
        d.line([cx-r, cy, cx+r, cy], fill="white", width=lw)          # equator
        yy, xx = r*0.55, r*0.83   # chord half-width = √(1−0.55²)·r
        d.line([cx-xx, cy-yy, cx+xx, cy-yy], fill="white", width=lw)  # parallels
        d.line([cx-xx, cy+yy, cx+xx, cy+yy], fill="white", width=lw)
    else:
        d.rounded_rectangle([2,2,size-2,size-2], radius=4, fill="#0891b2")
        d.ellipse([7,6,14,13], fill="#fef9c3")
        d.polygon([(4,size-6),(size//2,14),(size-4,size-6)], fill="#164e63")

    # Downscale from the supersampled raster, then convert to QPixmap
    img = img.resize((size, size), Image.LANCZOS)
    data = img.tobytes("raw", "RGBA")
    qimg = QImage(data, size, size, QImage.Format.Format_RGBA8888)
    return QPixmap.fromImage(qimg)


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
            self._press_pos   = event.globalPosition().toPoint()
            self._is_dragging = False
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
        try:
            super().mouseMoveEvent(event)
        except RuntimeError:
            pass

    def mouseReleaseEvent(self, event):
        if event.button() == Qt.MouseButton.LeftButton:
            if not self._is_dragging:
                itm = self.item
                QTimer.singleShot(0, lambda: self.sig_paste.emit(itm))
            self._press_pos   = None
            self._is_dragging = False
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
        self._close_timer  = QTimer(self)
        self._close_timer.setSingleShot(True)
        self._close_timer.timeout.connect(self._close_if_cursor_outside)

        # Rounded card + Qt drop shadow inside transparent margins —
        # same elevation recipe as the main popup.
        outer = QVBoxLayout(self)
        outer.setContentsMargins(8, 6, 8, 11)
        card = QWidget(self)
        card.setObjectName("panel_card")
        card.setStyleSheet(
            f"QWidget#panel_card {{background:{colours['bg']};"
            f"border:1px solid {colours['border']};border-radius:8px;}}")
        _shadow = QGraphicsDropShadowEffect(card)
        _shadow.setBlurRadius(18)
        _shadow.setOffset(0, 3)
        _shadow.setColor(QColor(0, 0, 0, 140))
        card.setGraphicsEffect(_shadow)
        outer.addWidget(card)

        lay = QVBoxLayout(card)
        lay.setContentsMargins(1, 1, 1, 7)   # bottom pad = rounded base
        lay.setSpacing(0)

        # Header — nested folder panels show the folder name
        hdr_text = (f"  {title} — {len(files)} files" if title
                    else f"  {len(files)} files")
        hdr = QLabel(hdr_text, self)
        hdr.setFont(QFont("Segoe UI", 9, QFont.Weight.Bold))
        hdr.setFixedHeight(28)
        hdr.setStyleSheet(
            f"background:{_grad_v(colours['accent_light'], _shade(colours['accent'], -0.18))};"
            f"color:white;padding-left:6px;"
            f"border-top-left-radius:7px;"
            f"border-top-right-radius:7px;"
            f"border-bottom:1px solid rgba(0,0,0,90);")
        lay.addWidget(hdr)
        self._hdr = hdr   # kept so per-file delete can update the count live

        # Scrollable list
        self._list = QListWidget(self)
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
        return False   # never consume — just observe

    def _on_file_click(self, item: QListWidgetItem):
        # itemClicked fires for right-clicks too — those open the menu,
        # they must not paste.
        if self._last_btn != Qt.MouseButton.LeftButton:
            return
        fp = item.data(Qt.ItemDataRole.UserRole)
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
        QTimer.singleShot(0, lambda: cb(fp))

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
        # Overlap the transparent shadow margins (8px each side) so the
        # visible cards sit ~2px apart with no dead zone for the cursor.
        if space_right >= pw or space_right >= space_left:
            px = my.right() - 14
        else:
            px = my.left() - pw + 14
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

            # Send to profile ▸  (named profiles only)
            profs = ([p for p in ctrl.profiles.get_all_profiles()
                      if not p.get("built_in")] if ctrl.profiles else [])
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
            if itype == "folder":
                try:
                    qi.setData(_COUNT_ROLE, len(os.listdir(fp)))
                except OSError:
                    pass   # unreadable folder — no count shown
            qi.setIcon(QIcon(_icon_pixmap(itype, 16)))
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

    def _send_file_to_profile(self, fp: str, profile_id: str, profile_name: str):
        # Single files sent to a profile become their own hidden history
        # entries (id = md5 of path) — visible in that profile, not General.
        ctrl  = self.controller
        hist  = ctrl.history
        fid   = hashlib.md5(fp.encode()).hexdigest()
        if hist._find_by_id(fid) is None:
            hist.items.insert(0, {
                "id":      fid,
                "type":    "file",
                "content": [fp],
                "source":  os.path.dirname(fp),
                "pinned":  False,
                "hidden":  True,
            })
            hist._save_history()
        ctrl.profiles.add_item_to_profile(fid, profile_id)
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

    def _build_and_show(self, x: int, y: int, keep_panel: bool = False):
        # Rebuild: close old windows but keep the session (paste target).
        # keep_panel=True only on _refresh — a fresh show() closes any
        # stale panel from the previous position.
        self._close_windows(keep_panel=keep_panel)

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

        outer = QVBoxLayout(popup)
        outer.setContentsMargins(10, 8, 10, 14)   # room for the shadow
        card = QWidget(popup)
        card.setObjectName("clipdrop_card")
        card.setStyleSheet(
            f"QWidget#clipdrop_card {{background:{C['bg']};"
            f"border:1px solid {C['border']};border-radius:10px;}}")
        _shadow = QGraphicsDropShadowEffect(card)
        _shadow.setBlurRadius(22)
        _shadow.setOffset(0, 4)
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

        # Connect search
        self._search_edit.textChanged.connect(self._on_search)

        # Escape to close
        from PyQt6.QtGui import QKeySequence, QShortcut
        sc = QShortcut(QKeySequence("Escape"), popup)
        sc.activated.connect(self.hide)

        # Build is complete — now size, position, THEN show.
        # Showing AFTER positioning means the window appears exactly where
        # it should on the first paint — no flash at 0,0 first.
        popup.adjustSize()
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

            # Both windows carry transparent shadow margins (popup 10px,
            # panel 8px) — overlap the frames so the visible cards sit
            # ~2px apart AND the cursor never crosses a dead zone between
            # windows (transparent pixels are click-through, so overlap
            # is harmless).
            if space_right >= pw or space_right >= space_left:
                px = pop.right() - 16           # flyout to the right
            else:
                px = pop.left() - pw + 16       # flyout to the left
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

        # Window height follows the item count
        if getattr(self, "_scroll", None) is not None:
            max_h = min(len(items) * ITEM_HEIGHT + 4, 480) if items else 100
            self._scroll.setFixedHeight(max_h)
            self._popup.adjustSize()

        # Close-behaviour setting may have changed
        self._start_hover_close_if_enabled()

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
