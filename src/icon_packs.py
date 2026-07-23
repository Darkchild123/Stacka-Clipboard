# ============================================================
# ClipDrop - icon_packs.py
# ============================================================
# Optional "Labeled" icon pack — a document-style set (white page +
# folded corner + glyph + extension badge), keyed PER FILE EXTENSION.
#
# The source SVGs carry their extension badge as an <text> element, which
# Qt's QSvgRenderer cannot draw. So we render the shape with Qt, then
# composite the badge back on with PIL (which loads the bold TTF directly
# and stays crisp). Icons are cached by (ext, size).
#
# Selected in Settings -> Icon pack. The Default pack lives in
# dropdown_popup.py. python / bash / text always use the Default icons.
# ============================================================

import re

from PIL import Image, ImageDraw, ImageFont
from PyQt6.QtGui  import QImage, QPixmap, QPainter
from PyQt6.QtCore import Qt, QByteArray
from PyQt6.QtSvg  import QSvgRenderer

_SS = 4                       # supersample the badge for crisp text
_CACHE: dict = {}
_FONT_CACHE: dict = {}


def _bold_font(px: int):
    if px in _FONT_CACHE:
        return _FONT_CACHE[px]
    font = None
    for name in ("arialbd.ttf", "segoeuib.ttf", "seguisb.ttf", "arial.ttf"):
        try:
            font = ImageFont.truetype(name, px)
            break
        except Exception:
            continue
    _FONT_CACHE[px] = font
    return font


# ── The labeled document icons (extension -> SVG). Badge is the bottom
#    <text>; the renderer extracts + composites it. xmlns corrected. ──
_NS = 'xmlns="http://www.w3.org/2000/svg"'
_PAGE = ('<path d="M6 2h14l6 6v22H6V2z" fill="#FFF" stroke="#E2E8F0" stroke-width="1.5"/>'
         '<path d="M20 2v6h6" fill="none" stroke="#E2E8F0" stroke-width="1.5"/>')


def _svg(glyph: str) -> str:
    return f'<svg {_NS} viewBox="0 0 32 32">{_PAGE}{glyph}</svg>'


# Each entry: (glyph markup, badge text, badge colour)
LABELED = {
 "pdf":   ('<path d="M11 14c0-2 1-4 2-4s1.5 2 1 4c3 0 4 2 5 3.5s1 2.5 0 2.5c-1 0-2-2.5-4-3.5-2 1-4.5 2-5.5 1.5s-.5-2.5 1.5-4z" fill="none" stroke="#EF4444" stroke-width="1.25" stroke-linejoin="round"/>', "PDF", "#EF4444"),
 "docx":  ('<path d="M10 13h12M10 16h12M10 19h7" fill="none" stroke="#2563EB" stroke-width="1.5" stroke-linecap="round"/>', "DOCX", "#2563EB"),
 "txt":   ('<path d="M10 12h12M10 15h12M10 18h12M10 21h8" fill="none" stroke="#64748B" stroke-width="1.25" stroke-linecap="round"/>', "TXT", "#64748B"),
 "rtf":   ('<path d="M11 13h10M11 16h7" fill="none" stroke="#0EA5E9" stroke-width="2" stroke-linecap="round"/>', "RTF", "#0EA5E9"),
 "pages": ('<path d="M16 11l4 4-2 5h-4l-2-5 4-4zM16 20v-3" fill="none" stroke="#F97316" stroke-width="1.25" stroke-linejoin="round"/>', "PAGES", "#F97316"),
 "xlsx":  ('<rect x="10" y="12" width="12" height="9" rx="1" fill="none" stroke="#10B981" stroke-width="1.25"/><path d="M10 15h12M14 12v9" fill="none" stroke="#10B981" stroke-width="1"/>', "XLSX", "#10B981"),
 "csv":   ('<g fill="#059669"><circle cx="12" cy="14" r="1"/><circle cx="16" cy="14" r="1"/><circle cx="20" cy="14" r="1"/><circle cx="12" cy="18" r="1"/><circle cx="16" cy="18" r="1"/><circle cx="20" cy="18" r="1"/></g>', "CSV", "#059669"),
 "numbers":('<path d="M11 20v-4M15 20v-7M19 20v-9" fill="none" stroke="#14B8A6" stroke-width="2" stroke-linecap="round"/>', "NUMBERS", "#14B8A6"),
 "ods":   ('<path d="M10 13h12M10 17h12" fill="none" stroke="#047857" stroke-width="1.5"/>', "ODS", "#047857"),
 "pptx":  ('<rect x="10" y="12" width="12" height="8" rx="1" fill="none" stroke="#F97316" stroke-width="1.25"/><circle cx="16" cy="16" r="2" fill="none" stroke="#F97316" stroke-width="1.25"/>', "PPTX", "#F97316"),
 "odp":   ('<path d="M11 17h10M16 12v5" fill="none" stroke="#EA580C" stroke-width="1.5"/>', "ODP", "#EA580C"),
 "jpg":   ('<rect x="10" y="12" width="12" height="8" rx="1" fill="none" stroke="#A855F7" stroke-width="1.25"/><circle cx="13" cy="15" r="1" fill="#A855F7"/><path d="M11 19l3-3 2 2 3-4 3 4" fill="none" stroke="#A855F7" stroke-width="1.25" stroke-linejoin="round"/>', "JPG", "#A855F7"),
 "png":   ('<rect x="10" y="12" width="12" height="8" rx="1" fill="none" stroke="#C084FC" stroke-width="1.25"/><path d="M10 17l3-2 4 3 2-1 3 2" fill="none" stroke="#C084FC" stroke-width="1.25" stroke-linejoin="round"/>', "PNG", "#C084FC"),
 "svg":   ('<circle cx="16" cy="13" r="1.5" fill="none" stroke="#EC4899" stroke-width="1.25"/><circle cx="11" cy="18" r="1.5" fill="none" stroke="#EC4899" stroke-width="1.25"/><circle cx="21" cy="18" r="1.5" fill="none" stroke="#EC4899" stroke-width="1.25"/><path d="M12.5 17L15 14.5M19.5 17L17 14.5" fill="none" stroke="#EC4899" stroke-width="1.25"/>', "SVG", "#EC4899"),
 "gif":   ('<path d="M12 16a4 4 0 1 1 8 0 4 4 0 0 1-8 0z" fill="none" stroke="#D946EF" stroke-width="1.25"/><path d="M18 13.5l3-1.5v4" fill="none" stroke="#D946EF" stroke-width="1.25" stroke-linejoin="round"/>', "GIF", "#D946EF"),
 "webp":  ('<path d="M11 16a5 5 0 0 1 10 0" fill="none" stroke="#06B6D4" stroke-width="1.5" stroke-linecap="round"/><circle cx="16" cy="16" r="1.5" fill="#06B6D4"/>', "WEBP", "#06B6D4"),
 "psd":   ('<rect x="9" y="11" width="14" height="8" rx="1" fill="#001833" stroke="#00C8FF" stroke-width="1"/>', "PSD", "#00C8FF"),
 "ai":    ('<rect x="9" y="11" width="14" height="8" rx="1" fill="#261300" stroke="#FF9A00" stroke-width="1"/>', "AI", "#FF9A00"),
 "indd":  ('<rect x="9" y="11" width="14" height="8" rx="1" fill="#230016" stroke="#FF1A90" stroke-width="1"/>', "INDD", "#FF1A90"),
 "mp4":   ('<polygon points="13 12 21 16 13 20" fill="none" stroke="#F43F5E" stroke-width="1.5" stroke-linejoin="round"/>', "MP4", "#F43F5E"),
 "mov":   ('<circle cx="16" cy="15" r="4" fill="none" stroke="#4B5563" stroke-width="1.5"/><path d="M16 11v8M12 15h8" fill="none" stroke="#4B5563" stroke-width="1.25"/>', "MOV", "#4B5563"),
 "avi":   ('<path d="M10 13h12l-2-2H12l-2 2z" fill="#3B82F6"/><rect x="10" y="14" width="12" height="5" fill="none" stroke="#3B82F6" stroke-width="1.25"/>', "AVI", "#3B82F6"),
 "mkv":   ('<rect x="10" y="12" width="12" height="8" rx="1" fill="none" stroke="#4F46E5" stroke-width="1.5"/><path d="M14 14l4 4m0-4l-4 4" fill="none" stroke="#4F46E5" stroke-width="1.5"/>', "MKV", "#4F46E5"),
 "wmv":   ('<path d="M11 12l4-1v4h-4zm5-1.25l5-1.25v5.5h-5zm-5 6.75h4v4l-4-1zm5 0h5v4.5l-5-1.25z" fill="#0284C7"/>', "WMV", "#0284C7"),
 "mp3":   ('<path d="M12 18a2 2 0 1 1-2-2 2 2 0 0 1 2 2zm10-2a2 2 0 1 1-2-2 2 2 0 0 1 2 2z" fill="#06B6D4"/><path d="M12 18V11l10-2v7" fill="none" stroke="#06B6D4" stroke-width="1.5" stroke-linecap="round" stroke-linejoin="round"/>', "MP3", "#06B6D4"),
 "wav":   ('<path d="M10 16h2l1-4 2 8 2-6 1 4 2-5 1 3h1" fill="none" stroke="#38BDF8" stroke-width="1.5" stroke-linecap="round" stroke-linejoin="round"/>', "WAV", "#38BDF8"),
 "aac":   ('<circle cx="16" cy="15" r="4" fill="none" stroke="#EAB308" stroke-width="1.5"/><path d="M14 15a2 2 0 0 1 4 0" fill="none" stroke="#EAB308" stroke-width="1.25"/>', "AAC", "#EAB308"),
 "flac":  ('<rect x="10" y="13" width="12" height="6" rx="1" fill="none" stroke="#22C55E" stroke-width="1.5"/><path d="M13 16h6" fill="none" stroke="#22C55E" stroke-width="1.25"/>', "FLAC", "#22C55E"),
 "zip":   ('<path d="M15 11h2m-2 2h2m-2 2h2m-3 2h4v3h-4z" fill="none" stroke="#D97706" stroke-width="1.5" stroke-linecap="round"/>', "ZIP", "#D97706"),
 "rar":   ('<rect x="11" y="11" width="10" height="3" rx="0.5" fill="#DC2626"/><rect x="11" y="15" width="10" height="3" rx="0.5" fill="#DC2626"/><path d="M14 10v9" fill="none" stroke="#E2E8F0" stroke-width="1.5"/>', "RAR", "#DC2626"),
 "7z":    ('<path d="M12 12h8l-5 8" fill="none" stroke="#4B5563" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"/>', "7Z", "#4B5563"),
 "gz":    ('<path d="M12 14l4-2 4 2v4l-4 2-4-2v-4z" fill="none" stroke="#9A3412" stroke-width="1.25"/><path d="M12 14l4 2 4-2M16 16v4" fill="none" stroke="#9A3412" stroke-width="1.25"/>', "TAR.GZ", "#9A3412"),
 "html":  ('<path d="M12 13l-4 3 4 3m8-6l4 3-4 3" fill="none" stroke="#EA580C" stroke-width="1.75" stroke-linecap="round" stroke-linejoin="round"/>', "HTML", "#EA580C"),
 "css":   ('<path d="M13 12h6l-1 6h-4l-0.5 3h5" fill="none" stroke="#2563EB" stroke-width="1.75" stroke-linecap="round" stroke-linejoin="round"/>', "CSS", "#2563EB"),
 "js":    ('<rect x="9" y="11" width="14" height="10" rx="1" fill="#FACC15"/>', "JS", "#CA8A04"),
 "json":  ('<path d="M13 12c-1 0-2 1-2 2v1c0 1-1 1-1 1s1 0 1 1v1c0 1 1 2 2 2m6-8c1 0 2 1 2 2v1c0 1 1 1 1 1s-1 0-1 1v1c0 1-1 2-2 2" fill="none" stroke="#F59E0B" stroke-width="1.5" stroke-linecap="round"/>', "JSON", "#F59E0B"),
 "php":   ('<ellipse cx="16" cy="15" rx="5" ry="3" fill="none" stroke="#8B5CF6" stroke-width="1.5"/>', "PHP", "#8B5CF6"),
 "java":  ('<path d="M11 16h8a0 0 0 0 1 0 0v2a3 3 0 0 1-3 3h-2a3 3 0 0 1-3-3v-2zm8 1h2a1 1 0 0 1 1 1v0a1 1 0 0 1-1 1h-2" fill="none" stroke="#B45309" stroke-width="1.25"/><path d="M13 13c1-1 0-2 1-3m2 3c1-1 0-2 1-3" fill="none" stroke="#B45309" stroke-width="1" stroke-linecap="round"/>', "JAVA", "#B45309"),
 "sql":   ('<ellipse cx="16" cy="12" rx="4" ry="1.5" fill="none" stroke="#DB2777" stroke-width="1.25"/><path d="M12 12v3c0 .8 1.8 1.5 4 1.5s4-.7 4-1.5v-3m-8 3v3c0 .8 1.8 1.5 4 1.5s4-.7 4-1.5v-3" fill="none" stroke="#DB2777" stroke-width="1.25"/>', "SQL", "#DB2777"),
 "exe":   ('<rect x="10" y="12" width="12" height="8" rx="1" fill="none" stroke="#475569" stroke-width="1.5"/><circle cx="16" cy="16" r="1.5" fill="#475569"/>', "EXE", "#475569"),
 "dll":   ('<circle cx="16" cy="15" r="3" fill="none" stroke="#94A3B8" stroke-width="1.5"/><path d="M16 11v2m0 4v2m-4-3h2m4 0h2" fill="none" stroke="#94A3B8" stroke-width="1.25" stroke-linecap="round"/>', "DLL", "#94A3B8"),
 "dmg":   ('<path d="M15.5 12.5c0-1.5 1-2 1-2s-1-.2-1.5.5c-.5.6-.3 1.5-.3 1.5s.8.2 1-.5zm.5 1.5c-1 0-2 .5-2 1.5s1 1.5 2 1.5 2-.5 2-1.5-1-1.5-2-1.5z" fill="#1F2937"/>', "DMG", "#1F2937"),
 "iso":   ('<circle cx="16" cy="15" r="4.5" fill="none" stroke="#78350F" stroke-width="1.5"/><circle cx="16" cy="15" r="1.5" fill="none" stroke="#78350F" stroke-width="1.25"/>', "ISO", "#78350F"),
 "app":   ('<polygon points="16 11 21 13.5 21 18.5 16 21 11 18.5 11 13.5" fill="none" stroke="#2563EB" stroke-width="1.25" stroke-linejoin="round"/><line x1="16" y1="11" x2="16" y2="21" stroke="#2563EB" stroke-width="1.25"/><line x1="11" y1="13.5" x2="16" y2="16" stroke="#2563EB" stroke-width="1.25"/><line x1="21" y1="13.5" x2="16" y2="16" stroke="#2563EB" stroke-width="1.25"/>', "APP", "#2563EB"),
 "lnk":   ('<circle cx="14" cy="19" r="5" fill="#fff" stroke="#64748B" stroke-width="1.25"/><path d="M12 21l5-5m-3.5 0h3.5v3.5" fill="none" stroke="#334155" stroke-width="1.5" stroke-linecap="round" stroke-linejoin="round"/>', "LNK", "#64748B"),
}

# 3D models & CAD — one shared "wireframe cube" glyph (same family as the
# "app" hexagon above, just its own colour), reused across every format so
# the whole category reads as one visual family; only the badge text (the
# real extension) differs per entry.
_M3D_GLYPH = ('<polygon points="16 10 21 13 21 19 16 22 11 19 11 13" '
              'fill="none" stroke="#1E3A8A" stroke-width="1.4" stroke-linejoin="round"/>'
              '<path d="M11 13l5 3 5-3M16 16v6" fill="none" stroke="#1E3A8A" '
              'stroke-width="1.2" stroke-linejoin="round"/>')
_M3D_COL = "#1E3A8A"

for _ext, _badge in [
    ("step", "STEP"), ("iges", "IGES"), ("stl", "STL"), ("3mf", "3MF"),
    ("obj", "OBJ"), ("fbx", "FBX"), ("dwg", "DWG"), ("dxf", "DXF"),
    ("sldprt", "SLDPRT"), ("sldasm", "SLDASM"), ("slddrw", "SLDDRW"),
    ("ipt", "IPT"), ("iam", "IAM"), ("idw", "IDW"), ("ipn", "IPN"),
    ("catpart", "CATPART"), ("catproduct", "CATPRODUCT"), ("catdrawing", "CATDRAWING"),
    ("x_t", "X_T"), ("x_b", "X_B"),
    ("3dm", "3DM"), ("skp", "SKP"), ("blend", "BLEND"),
    ("gltf", "GLTF"), ("glb", "GLB"), ("dae", "DAE"),
    ("rvt", "RVT"), ("rfa", "RFA"), ("rte", "RTE"),
    ("ifc", "IFC"), ("gcode", "GCODE"),
    ("ply", "PLY"), ("amf", "AMF"), ("wrl", "WRL"), ("x3d", "X3D"), ("u3d", "U3D"),
    ("ma", "MA"), ("mb", "MB"), ("c4d", "C4D"), ("lwo", "LWO"),
    ("3ds", "3DS"), ("max", "MAX"),
    ("scad", "SCAD"), ("fcstd", "FCSTD"), ("sat", "SAT"), ("jt", "JT"),
]:
    LABELED[_ext] = (_M3D_GLYPH, _badge, _M3D_COL)

# Secondary extensions that share an icon
_ALIASES = {
 "doc": "docx", "xls": "xlsx", "ppt": "pptx", "jpeg": "jpg",
 "htm": "html", "scss": "css", "tar": "gz", "tgz": "gz", "sys": "dll",
 "mpeg": "mp4", "m4v": "mp4", "wma": "wmv", "m4a": "mp3", "ogg": "mp3",
 "stp": "step", "igs": "iges", "gco": "gcode",   # true format-variant extensions
}
# NOTE: .url / .webloc (internet shortcuts) are deliberately NOT aliased here
# — they fall through to the Default pack's "url" icon (see dropdown_popup.py
# _FILE_TYPE_MAP), so they read as links, never as an app shortcut.


def _extract(size: int, ext: str):
    key = LABELED.get(ext) or LABELED.get(_ALIASES.get(ext, ""))
    return key


def labeled_pixmap(ext: str, size: int):
    """QPixmap for a file extension in the Labeled pack, or None if this
    pack doesn't define it (caller falls back to the Default pack)."""
    ext = (ext or "").lower().lstrip(".")
    spec = LABELED.get(ext) or LABELED.get(_ALIASES.get(ext, ""))
    if spec is None:
        return None
    ckey = (ext, size)
    if ckey in _CACHE:
        return _CACHE[ckey]
    glyph, badge, colour = spec
    # 1) render the page + glyph via Qt (its <text> is ignored anyway)
    r = QSvgRenderer(QByteArray(_svg(glyph).encode("utf-8")))
    qimg = QImage(size, size, QImage.Format.Format_ARGB32)
    qimg.fill(Qt.GlobalColor.transparent)
    p = QPainter(qimg)
    p.setRenderHint(QPainter.RenderHint.Antialiasing)
    r.render(p)
    p.end()
    # 2) composite the badge with PIL (crisp bold text Qt SVG can't draw)
    qimg = qimg.convertToFormat(QImage.Format.Format_RGBA8888)
    ptr = qimg.constBits(); ptr.setsize(qimg.sizeInBytes())
    pil = Image.frombytes("RGBA", (size, size), bytes(ptr)).copy()
    big = pil.resize((size*_SS, size*_SS), Image.LANCZOS)
    d = ImageDraw.Draw(big)
    ratio = 0.16 if len(badge) <= 3 else (0.13 if len(badge) <= 4 else 0.11)
    f = _bold_font(max(6, int(size*_SS*ratio)))
    if f:
        d.text((size*_SS*0.5, size*_SS*0.84), badge, font=f, fill=colour, anchor="mm")
    pil = big.resize((size, size), Image.LANCZOS)
    data = pil.tobytes("raw", "RGBA")
    out = QPixmap.fromImage(QImage(data, size, size, QImage.Format.Format_RGBA8888))
    _CACHE[ckey] = out
    return out
