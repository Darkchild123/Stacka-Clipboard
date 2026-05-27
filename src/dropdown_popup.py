# ============================================================
# ClipDrop - dropdown_popup.py
# ============================================================
# The main visual interface of ClipDrop.
# Shows a popup list at the cursor with all clipboard items.
#
# FIX: No longer creates its own Tk() instance. Instead it
# receives the shared root from main.py and uses root.after()
# to safely trigger UI updates from any thread.
# ============================================================

import tkinter as tk
from PIL import Image, ImageTk, ImageDraw
import win32clipboard
import win32con
import win32gui
import pyautogui
import os
import time
import io

DRAG_THRESHOLD = 6   # pixels of movement before drag mode activates


# --- Colour themes ---
DARK_COLOURS = {
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

LIGHT_COLOURS = {
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

# Active theme — updated at runtime based on saved settings
COLOURS = DARK_COLOURS

# Left-edge accent colour per item type — makes item type scannable at a glance
TYPE_COLOURS = {
    "text":   "#4f46e5",  # indigo
    "url":    "#0ea5e9",  # sky blue
    "file":   "#f59e0b",  # amber
    "folder": "#f59e0b",  # amber
    "code":   "#7c3aed",  # violet
    "bash":   "#16a34a",  # green
    "image":  "#0891b2",  # teal
}

FONT_PREVIEW = ("Segoe UI", 10)
FONT_SOURCE  = ("Segoe UI", 8)

POPUP_WIDTH  = 400
MAX_HEIGHT   = 500
ITEM_HEIGHT  = 72
THUMB_SIZE   = 36
PADDING      = 10

# Maps every known file extension to an icon-type string used by _draw_type_icon.
# Extensions not listed here fall back to the generic amber "file" icon.
_FILE_TYPE_MAP = {}
for _e in ['.png','.jpg','.jpeg','.gif','.bmp','.webp','.ico','.tiff','.tif','.heic','.avif','.svg']:
    _FILE_TYPE_MAP[_e] = "image"
for _e in ['.mp4','.mov','.avi','.mkv','.wmv','.flv','.webm','.m4v','.mpg','.mpeg','.3gp','.ts','.vob','.rm','.rmvb']:
    _FILE_TYPE_MAP[_e] = "video"
for _e in ['.mp3','.wav','.flac','.aac','.ogg','.m4a','.wma','.opus','.aiff','.alac']:
    _FILE_TYPE_MAP[_e] = "audio"
for _e in ['.xlsx','.xls','.xlsm','.xlsb','.ods','.numbers','.csv','.tsv']:
    _FILE_TYPE_MAP[_e] = "excel"
for _e in ['.docx','.doc','.odt','.rtf','.pages','.docm']:
    _FILE_TYPE_MAP[_e] = "word"
for _e in ['.pptx','.ppt','.odp','.key','.pptm']:
    _FILE_TYPE_MAP[_e] = "ppt"
for _e in ['.pdf']:
    _FILE_TYPE_MAP[_e] = "pdf"
for _e in ['.exe','.msi','.apk','.dmg','.deb','.rpm','.jar','.appx','.msix']:
    _FILE_TYPE_MAP[_e] = "exe"
for _e in ['.zip','.rar','.7z','.tar','.gz','.bz2','.xz','.zst','.cab','.iso']:
    _FILE_TYPE_MAP[_e] = "zip"
for _e in ['.html','.htm','.xhtml','.mhtml','.php','.asp','.aspx','.jsp']:
    _FILE_TYPE_MAP[_e] = "html"
for _e in ['.py','.js','.ts','.jsx','.tsx','.java','.c','.cpp','.h','.cs',
           '.go','.rs','.rb','.swift','.kt','.r','.sql','.css','.scss','.less',
           '.vue','.svelte','.lua','.bat','.cmd','.sh','.bash','.ps1','.vbs']:
    _FILE_TYPE_MAP[_e] = "code"
for _e in ['.txt','.md','.log','.ini','.cfg','.conf','.json','.xml','.yaml','.yml','.toml']:
    _FILE_TYPE_MAP[_e] = "text"


class DropdownPopup:

    # Shared PIL-image cache for type icons.
    # Key: (icon_type, size)  →  Value: PIL Image (read-only after drawing).
    # Eliminates redundant re-drawing when many files share the same type,
    # e.g. 100 .jpg files all need the same 20-px "image" icon.
    _icon_cache: dict = {}

    def __init__(self, root, history_manager, watcher=None, profile_manager=None):
        """
        root            — the shared tkinter root from main.py
        history_manager — the app's history manager
        watcher         — the clipboard watcher (so we can pause it during paste)
        profile_manager — manages profiles and active profile selection
        """
        self.root     = root
        self.history  = history_manager
        self.watcher  = watcher           # Used to pause watching during paste
        self.profiles = profile_manager   # Profile filtering and switching
        self.window   = None              # The popup Toplevel window
        self.thumbnails = []              # Keep image references alive

        # Drag state — used to track window repositioning (header drag)
        self._drag_x = 0
        self._drag_y = 0

        # Item drag-and-drop state
        self._drag_item    = None   # Item being dragged
        self._drag_ghost   = None   # Ghost Toplevel that follows the cursor
        self._drag_start_x = 0
        self._drag_start_y = 0
        self._is_dragging  = False

        # Bind Escape key globally to close popup
        self.root.bind_all("<Escape>", lambda e: self.hide())


    # ============================================================
    # SHOW & HIDE
    # ============================================================

    def show(self, x, y):
        """
        Safely schedules the popup to appear at (x, y).
        Uses root.after() so it always runs on the main thread,
        even when called from a hotkey or background thread.
        """
        # Only capture from OS if the caller didn't pre-set the target
        # (context_menu.py sets it at right-click time for better accuracy).
        if not getattr(self, "_paste_target", None):
            try:
                import win32gui as _wg
                self._paste_target = _wg.GetForegroundWindow()
            except Exception:
                self._paste_target = None
        self.root.after(0, lambda: self._build_and_show(x, y))


    def hide(self):
        """
        Safely schedules the popup to hide.
        Uses root.after() for thread safety.
        """
        self.root.after(0, self._do_hide)


    def _do_hide(self):
        """Actually hides/destroys the popup window."""
        if self.window:
            try:
                self.window.destroy()
            except Exception:
                pass
            self.window = None


    def _build_and_show(self, x, y):
        """
        Builds and displays the popup window.
        Always runs on the main thread via root.after().
        Uses Toplevel — a child window of root — instead of Tk().
        This is the correct tkinter pattern for multi-window apps.
        """
        # Apply the current theme and transparency from saved settings
        global COLOURS
        theme = self.history.settings.get("theme", "dark")
        COLOURS = DARK_COLOURS if theme == "dark" else LIGHT_COLOURS
        self._opacity = self.history.settings.get("transparency", 1.0)

        # Destroy any existing popup first
        self._do_hide()

        self.thumbnails = []
        # Use active profile's filtered items if profiles are available,
        # otherwise fall back to full history.
        # If the active named profile is empty, automatically switch back to
        # General so the user always sees their history, not a blank popup.
        if self.profiles:
            items = self.profiles.get_active_items()
            active = self.profiles.get_active_profile()
            if not items and not active.get("built_in"):
                self.profiles.set_active("general")
                items = self.profiles.get_active_items()
        else:
            items = self.history.get_all()

        # Create a Toplevel window — child of root, not a new Tk()
        self.window = tk.Toplevel(self.root)
        self.window.overrideredirect(True)   # No title bar
        self.window.attributes("-topmost", True)
        self.window.configure(bg=COLOURS["bg"])

        # WS_EX_NOACTIVATE — window receives mouse clicks but NEVER steals
        # keyboard focus from the app the user wants to paste into.
        # This is the correct fix: if we never take focus, we never need to
        # restore it before sending Ctrl+V.
        try:
            import win32gui, win32con
            _hw = self.window.winfo_id()
            _ex = win32gui.GetWindowLong(_hw, win32con.GWL_EXSTYLE)
            win32gui.SetWindowLong(_hw, win32con.GWL_EXSTYLE,
                                   _ex | win32con.WS_EX_NOACTIVATE)
        except Exception:
            pass

        # Hide until fully built to prevent flicker
        self.window.withdraw()

        # Escape still works via the mouse-hook left-click detection
        self.window.bind("<Escape>", lambda e: self.hide())

        if not items:
            self._build_empty_state()
        else:
            self._build_content(items)

        # Position on screen before showing
        self.window.update_idletasks()
        self._position_popup(x, y)

        # Fade in smoothly from transparent to fully visible
        self.window.attributes("-alpha", 0.0)
        self.window.deiconify()
        self.window.lift()
        self._fade_in()


    def _show_toast(self, message, duration=2000):
        """
        Shows a brief floating notification above the popup window.

        Positioned ABOVE the popup so it is never covered by it.
        Dark charcoal background (clearly distinct from the purple theme)
        with 70 % opacity so the desktop shows through slightly.
        Font size 12 so the message is easy to read at a glance.
        Default duration is 2 seconds; fades out smoothly after that.
        """
        TOAST_BG    = "#1c1c1c"   # Near-black charcoal — not purple
        TOAST_FG    = "#fbbf24"   # Amber text — high contrast on dark bg
        TOAST_ALPHA = 0.70        # 70 % opacity — clearly transparent

        toast = tk.Toplevel(self.root)
        toast.overrideredirect(True)
        toast.attributes("-topmost", True)
        toast.attributes("-alpha", TOAST_ALPHA)
        toast.configure(bg=TOAST_BG)

        tk.Label(
            toast, text=message,
            bg=TOAST_BG, fg=TOAST_FG,
            font=("Segoe UI", 12, "bold"),
            padx=20, pady=12
        ).pack()

        toast.update_idletasks()
        th = toast.winfo_reqheight()
        tw = toast.winfo_reqwidth()

        # Position ABOVE the popup so it is never overlapped by the dropdown.
        # Falls back to just above the cursor when no popup is open.
        if self.window:
            wx = self.window.winfo_x()
            wy = self.window.winfo_y()
            toast_x = wx + (POPUP_WIDTH // 2) - (tw // 2)
            toast_y = max(0, wy - th - 8)         # 8 px gap above the popup
        else:
            cx, cy = pyautogui.position()
            toast_x = cx - (tw // 2)
            toast_y = max(0, cy - th - 16)

        toast.geometry(f"+{toast_x}+{toast_y}")
        toast.lift()

        # Fade out smoothly after `duration` ms
        def _fade_out(alpha=TOAST_ALPHA):
            if not toast.winfo_exists():
                return
            alpha -= 0.07
            if alpha <= 0:
                toast.destroy()
                return
            toast.attributes("-alpha", alpha)
            self.root.after(40, lambda: _fade_out(alpha))

        self.root.after(duration, lambda: _fade_out() if toast.winfo_exists() else None)


    def _fade_in(self, alpha=0.0):
        """
        Smoothly fades the popup in to the user's chosen transparency level.
        Steps up opacity by 0.08 every 15ms.
        """
        if not self.window:
            return
        target = getattr(self, "_opacity", 1.0)
        alpha  = min(alpha + 0.08, target)
        try:
            self.window.attributes("-alpha", alpha)
        except Exception:
            return
        if alpha < target:
            self.root.after(15, lambda: self._fade_in(alpha))


    # ============================================================
    # BUILDING CONTENT
    # ============================================================

    def _build_content(self, items):
        """Builds the header, search bar, and scrollable item list."""

        # Border frame
        border = tk.Frame(self.window, bg=COLOURS["border"], padx=1, pady=1)
        border.pack(fill="both", expand=True)

        inner = tk.Frame(border, bg=COLOURS["bg"])
        inner.pack(fill="both", expand=True)

        # Header — drag handle + profile switcher
        header = tk.Frame(inner, bg=COLOURS["accent"], height=36)
        header.pack(fill="x")
        header.pack_propagate(False)

        lbl_title = tk.Label(
            header, text="📋  ClipDrop",
            bg=COLOURS["accent"], fg="white",
            font=("Segoe UI", 10, "bold"), padx=PADDING
        )
        lbl_title.pack(side="left", fill="y")

        count_label = tk.Label(
            header, text=f"{len(items)} items",
            bg=COLOURS["accent"], fg="#c7d2fe",
            font=FONT_SOURCE, padx=PADDING
        )
        count_label.pack(side="right", fill="y")

        # Profile switcher — shows active profile name with a dropdown arrow.
        # Clicking it opens a menu to switch profiles.
        if self.profiles:
            active_name = self.profiles.get_active_profile()["name"]
            lbl_profile = tk.Label(
                header, text=f"{active_name}  ▾",
                bg=COLOURS["accent"], fg="#c7d2fe",
                font=("Segoe UI", 8, "bold"),
                padx=6, cursor="hand2"
            )
            lbl_profile.pack(side="right", fill="y")
            lbl_profile.bind("<Button-1>",
                lambda e, lbl=lbl_profile: self._show_profile_menu(lbl))
            lbl_profile.bind("<Enter>",
                lambda e: lbl_profile.configure(fg="white"))
            lbl_profile.bind("<Leave>",
                lambda e: lbl_profile.configure(fg="#c7d2fe"))

        # Make title and count draggable (not the profile switcher)
        for widget in (header, lbl_title, count_label):
            self._make_draggable(widget)

        # --- Search bar ---
        # Lets the user type to instantly filter clipboard history.
        # Matches against preview text, source, and item type.
        search_bg = COLOURS["bg_item"]
        search_outer = tk.Frame(inner, bg=search_bg)
        search_outer.pack(fill="x")

        search_row = tk.Frame(search_outer, bg=search_bg)
        search_row.pack(fill="x", padx=8, pady=5)

        tk.Label(
            search_row, text="🔍",
            bg=search_bg, fg=COLOURS["text_dim"],
            font=("Segoe UI", 9)
        ).pack(side="left", padx=(2, 4))

        self._search_var = tk.StringVar()
        search_entry = tk.Entry(
            search_row, textvariable=self._search_var,
            bg=search_bg, fg=COLOURS["text"],
            insertbackground=COLOURS["text"],
            relief="flat", font=("Segoe UI", 10),
            bd=0, highlightthickness=0
        )
        search_entry.pack(side="left", fill="x", expand=True, ipady=2)

        clear_btn = tk.Label(
            search_row, text="✕",
            bg=search_bg, fg=COLOURS["text_dim"],
            font=("Segoe UI", 9), cursor="hand2", padx=4
        )
        clear_btn.pack(side="right")
        clear_btn.bind("<Button-1>", lambda e: self._search_var.set(""))
        clear_btn.bind("<Enter>", lambda e: clear_btn.configure(fg=COLOURS["danger"]))
        clear_btn.bind("<Leave>", lambda e: clear_btn.configure(fg=COLOURS["text_dim"]))

        # Thin separator under search bar
        tk.Frame(inner, bg=COLOURS["border"], height=1).pack(fill="x")

        # --- Scrollable canvas ---
        content_height = min(len(items) * ITEM_HEIGHT, MAX_HEIGHT)

        canvas = tk.Canvas(
            inner, bg=COLOURS["bg"],
            width=POPUP_WIDTH, height=content_height,
            highlightthickness=0
        )
        # Store ref so _build_item_row can update scrollregion after expand/collapse
        self._scroll_canvas = canvas

        scrollbar = tk.Scrollbar(inner, orient="vertical", command=canvas.yview)
        canvas.configure(yscrollcommand=scrollbar.set)

        if len(items) * ITEM_HEIGHT > MAX_HEIGHT:
            scrollbar.pack(side="right", fill="y")

        canvas.pack(side="left", fill="both", expand=True)

        items_frame = tk.Frame(canvas, bg=COLOURS["bg"])
        canvas.create_window((0, 0), window=items_frame, anchor="nw")

        def _rebuild_items(filtered):
            """Clears and rebuilds the items list from the filtered set."""
            for w in items_frame.winfo_children():
                w.destroy()
            if filtered:
                for index, item in enumerate(filtered):
                    self._build_item_row(items_frame, item, index)
            else:
                tk.Label(
                    items_frame,
                    text="No results found",
                    bg=COLOURS["bg"], fg=COLOURS["text_dim"],
                    font=FONT_PREVIEW, padx=20, pady=20
                ).pack()
            items_frame.update_idletasks()
            canvas.configure(scrollregion=canvas.bbox("all"))
            # Update item count in the header
            if len(filtered) < len(items):
                count_label.configure(text=f"{len(filtered)} / {len(items)} items")
            else:
                count_label.configure(text=f"{len(items)} items")

        _rebuild_items(items)

        def _on_search(*args):
            """Re-filters the item list every time the search text changes."""
            query = self._search_var.get().strip().lower()
            if not query:
                _rebuild_items(items)
                return
            filtered = [
                i for i in items
                if query in self.history.get_preview(i).lower()
                or query in i.get("source", "").lower()
                or query in i.get("type", "").lower()
            ]
            _rebuild_items(filtered)

        self._search_var.trace_add("write", _on_search)

        canvas.bind_all("<MouseWheel>",
            lambda e: canvas.yview_scroll(int(-1 * (e.delta / 120)), "units"))


    def _build_empty_state(self):
        """Shows a message when history is empty."""
        border = tk.Frame(self.window, bg=COLOURS["border"], padx=1, pady=1)
        border.pack(fill="both", expand=True)
        inner = tk.Frame(border, bg=COLOURS["bg"])
        inner.pack(fill="both", expand=True)

        # Header (draggable even on empty state)
        header = tk.Frame(inner, bg=COLOURS["accent"], height=36)
        header.pack(fill="x")
        header.pack_propagate(False)
        lbl = tk.Label(
            header, text="📋  ClipDrop",
            bg=COLOURS["accent"], fg="white",
            font=("Segoe UI", 10, "bold"), padx=PADDING
        )
        lbl.pack(side="left", fill="y")
        self._make_draggable(header)
        self._make_draggable(lbl)

        tk.Label(
            inner,
            text="📋\n\nNo clipboard history yet.\nCopy something to get started!",
            bg=COLOURS["bg"], fg=COLOURS["text_dim"],
            font=FONT_PREVIEW, padx=20, pady=24,
            justify="center"
        ).pack(expand=True)


    @staticmethod
    def _hex_lerp(c1, c2, t):
        """
        Linearly interpolate between two hex colour strings.
        t=0.0 → c1 exactly,  t=1.0 → c2 exactly.  Clamps t to [0, 1].
        Used by the hover animation to smoothly blend background colours.
        """
        t  = max(0.0, min(1.0, t))
        r1, g1, b1 = int(c1[1:3], 16), int(c1[3:5], 16), int(c1[5:7], 16)
        r2, g2, b2 = int(c2[1:3], 16), int(c2[3:5], 16), int(c2[5:7], 16)
        r = int(r1 + (r2 - r1) * t)
        g = int(g1 + (g2 - g1) * t)
        b = int(b1 + (b2 - b1) * t)
        return f"#{r:02x}{g:02x}{b:02x}"


    def _update_scroll(self):
        """
        Recalculates the scrollable canvas region.
        Called every animation frame during expand/collapse so the scrollable
        area always matches the actual (partially-animated) content height.
        """
        try:
            if hasattr(self, "_scroll_canvas") and self._scroll_canvas.winfo_exists():
                self._scroll_canvas.configure(
                    scrollregion=self._scroll_canvas.bbox("all")
                )
        except Exception:
            pass


    def _build_item_row(self, parent, item, index):
        """Builds one row for a single clipboard item."""
        is_pinned = item.get("pinned", False)
        bg = COLOURS["bg_pinned"] if is_pinned else (
            COLOURS["bg"] if index % 2 == 0 else COLOURS["bg_item"]
        )

        row = tk.Frame(parent, bg=bg, height=ITEM_HEIGHT, width=POPUP_WIDTH)
        row.pack(fill="x")
        row.pack_propagate(False)

        # Colored left-edge strip — shows item type at a glance without looking at the icon
        # Each type has its own color: indigo=text, sky=url, amber=file, violet=code, green=bash, teal=image
        type_strip_colour = TYPE_COLOURS.get(item["type"], COLOURS["accent"])
        strip = tk.Frame(row, bg=type_strip_colour, width=3)
        strip.pack(side="left", fill="y")
        strip.pack_propagate(False)

        # Thin separator line between items
        sep = tk.Frame(parent, bg=COLOURS["border"], height=1)
        sep.pack(fill="x")

        # Thumbnail — left column
        thumb_frame = tk.Frame(row, bg=bg, width=THUMB_SIZE + 6)
        thumb_frame.pack(side="left", fill="y", padx=(6, 2))
        thumb_frame.pack_propagate(False)
        self._build_thumbnail(thumb_frame, item, bg)

        # Action buttons — MUST be packed on the RIGHT before text_frame is packed.
        # In tkinter pack, if a widget with expand=True is packed first it claims all
        # remaining space, leaving zero width for any side="right" widget packed after.
        # Packing btn_frame first reserves its space; text_frame then fills what's left.
        #
        #   col 0  col 1
        #   📌     ↑
        #   ✕      ↓
        btn_frame = tk.Frame(row, bg=bg)
        btn_frame.pack(side="right", fill="y", padx=(0, 6), anchor="center")

        pin_colour = COLOURS["pin"] if is_pinned else COLOURS["text_dim"]
        grid_btns = [
            ("📌", lambda i=item: self._toggle_pin(i),  pin_colour,          0, 0),
            ("↑",  lambda i=item: self._move_up(i),     COLOURS["text_dim"], 0, 1),
            ("✕",  lambda i=item: self._delete_item(i), COLOURS["danger"],   1, 0),
            ("↓",  lambda i=item: self._move_down(i),   COLOURS["text_dim"], 1, 1),
        ]
        for text, cmd, colour, r, c in grid_btns:
            btn = tk.Label(
                btn_frame, text=text,
                bg=COLOURS["bg_item"], fg=colour,
                font=("Segoe UI", 10),
                padx=5, pady=4, cursor="hand2"
            )
            btn.grid(row=r, column=c, padx=2, pady=2)
            btn.bind("<Button-1>", lambda e, c=cmd: (c(), "break")[1])
            btn.bind("<Enter>", lambda e, b=btn: b.configure(bg=COLOURS["bg_hover"]))
            btn.bind("<Leave>", lambda e, b=btn: b.configure(bg=COLOURS["bg_item"]))

        # Preview and source text — packed AFTER btn_frame so expand=True only
        # fills the space that btn_frame hasn't already claimed on the right.
        text_frame = tk.Frame(row, bg=bg)
        text_frame.pack(side="left", fill="both", expand=True, pady=(4, 4))

        preview = self.history.get_preview(item)

        preview_label = tk.Label(
            text_frame, text=preview,
            bg=bg, fg=COLOURS["text_preview"],
            font=FONT_PREVIEW, anchor="nw",
            wraplength=220, justify="left"
        )
        preview_label.pack(anchor="w", fill="x")

        source_label = tk.Label(
            text_frame, text=f"From: {item.get('source', 'Unknown')}",
            bg=bg, fg=COLOURS["text_dim"],
            font=FONT_SOURCE, anchor="w"
        )
        source_label.pack(anchor="w")

        # Left-click: paste or drag-to-drop
        for widget in [row, text_frame, preview_label, source_label]:
            widget.bind("<ButtonPress-1>",   lambda e, i=item: self._on_item_press(e, i))
            widget.bind("<B1-Motion>",       lambda e, i=item: self._on_item_drag(e, i))
            widget.bind("<ButtonRelease-1>", lambda e, i=item: self._on_item_release(e, i))

        # Right-click: "Send to profile" context menu
        if self.profiles:
            for widget in [row, text_frame, preview_label, source_label]:
                widget.bind("<Button-3>",
                    lambda e, i=item: self._show_send_to_menu(e, i))

        # ── Hover / focus animation ───────────────────────────────────────
        # Smooth 16 ms-frame animation that runs on the main tkinter thread
        # via root.after().  When the mouse enters the row it animates toward
        # t=1 (fully highlighted); leaving animates back to t=0 (idle).
        #
        # Visual effects applied at each frame:
        #   • Row background fades:  normal bg  →  bg_hover
        #   • Left type-strip grows: 3 px → 5 px
        #   • Bottom separator tints toward the item's type colour (70 % blend)
        #   • Preview text colour brightens toward full white
        #
        # _anim["seq"] acts as a cancellation token: incrementing it makes any
        # still-running after() chain abort on its next tick, so Enter and Leave
        # events never fight each other.
        _anim = {"t": 0.0, "seq": 0}

        # All widgets that receive a background update during the fade.
        # btn_frame is included so its bg matches the row — the buttons inside
        # it keep their own explicit bg and are unaffected.
        _bg_widgets = [row, thumb_frame, text_frame,
                       preview_label, source_label, btn_frame]

        def _apply_state(t):
            """Push all visual effects at interpolation position t (0=idle, 1=hovered)."""
            if not row.winfo_exists():
                return
            new_bg = DropdownPopup._hex_lerp(bg, COLOURS["bg_hover"], t)
            for w in _bg_widgets:
                try:
                    w.configure(bg=new_bg)
                except Exception:
                    pass
            # Also update the icon/thumbnail label that lives inside thumb_frame
            for child in thumb_frame.winfo_children():
                try:
                    child.configure(bg=new_bg)
                except Exception:
                    pass
            # Left type-strip grows 3 px → 10 px — much more visible than before
            try:
                strip.configure(width=max(3, int(3 + 7 * t)))
            except Exception:
                pass
            # Bottom separator glows from border colour → full type colour
            sep_col = DropdownPopup._hex_lerp(COLOURS["border"], type_strip_colour, t)
            try:
                sep.configure(bg=sep_col)
            except Exception:
                pass
            # Preview text brightens from text_preview → text
            txt_col = DropdownPopup._hex_lerp(COLOURS["text_preview"], COLOURS["text"], t)
            try:
                preview_label.configure(fg=txt_col)
            except Exception:
                pass

        def _step(target_t, seq):
            """One animation frame: ease-out toward target_t, then reschedule."""
            if not row.winfo_exists():
                return
            if seq != _anim["seq"]:   # A newer animation event took over — abort.
                return
            diff = target_t - _anim["t"]
            if abs(diff) < 0.015:     # Close enough — snap to target and stop.
                _anim["t"] = target_t
                _apply_state(target_t)
                return
            _anim["t"] += diff * 0.45  # Ease-out: cover 45 % of remaining gap per frame
            _apply_state(_anim["t"])
            self.root.after(16, lambda: _step(target_t, seq))

        def _enter(e):
            _anim["seq"] += 1
            _step(1.0, _anim["seq"])

        def _leave(e):
            _anim["seq"] += 1
            _step(0.0, _anim["seq"])

        # Bind to all visual child widgets so hovering anywhere in the row
        # triggers the animation — NOT the action buttons (they have their own
        # individual hover styling and would conflict).
        for _w in [row, thumb_frame, text_frame, preview_label, source_label]:
            _w.bind("<Enter>", _enter)
            _w.bind("<Leave>", _leave)

        # ── Multi-file side panel ────────────────────────────────────────────
        # When the item holds 2+ files, hovering the row opens a floating side
        # panel to the right of the popup.  It lists every file in a compact
        # 32 px format with its own scrollbar.  The panel stays open as long as
        # the mouse is anywhere over the row OR the panel itself; it auto-closes
        # 250 ms after the mouse leaves both.
        # Left-click any file → pastes just that one file.
        # Right-click any file → Send-to-profile menu for the whole item.
        _files    = item.get("content", [])
        _is_multi = (
            item["type"] == "file"
            and isinstance(_files, list)
            and len(_files) > 1
        )

        if _is_multi:
            _n   = len(_files)
            _pst = {"win": None, "after_id": None}   # per-row panel state

            PANEL_W    = 340
            ROW_H      = 40
            MAX_LIST_H = 420

            def _cancel_close(_ps=_pst):
                if _ps["after_id"]:
                    self.root.after_cancel(_ps["after_id"])
                    _ps["after_id"] = None

            def _schedule_close(_ps=_pst):
                _cancel_close(_ps)
                def _do_close(_ps=_ps):
                    if _ps["win"] and _ps["win"].winfo_exists():
                        _ps["win"].destroy()
                    _ps["win"] = None
                    _ps["after_id"] = None
                _ps["after_id"] = self.root.after(250, _do_close)

            def _open_panel(_ps=_pst):
                _cancel_close(_ps)
                if _ps["win"] and _ps["win"].winfo_exists():
                    return   # already open
                if not (self.window and self.window.winfo_exists()):
                    return

                panel = tk.Toplevel(self.root)
                panel.overrideredirect(True)
                panel.attributes("-topmost", True)
                panel.configure(bg=COLOURS["border"])
                _ps["win"] = panel
                # Non-activating — clicks register without stealing focus
                try:
                    import win32gui, win32con
                    _ph = panel.winfo_id()
                    _pe = win32gui.GetWindowLong(_ph, win32con.GWL_EXSTYLE)
                    win32gui.SetWindowLong(_ph, win32con.GWL_EXSTYLE,
                                           _pe | win32con.WS_EX_NOACTIVATE)
                except Exception:
                    pass

                # ── Position ─────────────────────────────────────────────────
                popup_x = self.window.winfo_x()
                row_y   = row.winfo_rooty()
                panel_x = popup_x + POPUP_WIDTH + 4   # right of the main popup

                scr_w = self.window.winfo_screenwidth()
                scr_h = self.window.winfo_screenheight()

                if panel_x + PANEL_W > scr_w:          # flip left if near edge
                    panel_x = popup_x - PANEL_W - 4

                list_h  = min(_n * (ROW_H + 1), MAX_LIST_H)
                total_h = list_h + 36                   # 36 px header
                if row_y + total_h > scr_h:
                    row_y = max(0, scr_h - total_h - 8)

                # ── Content ───────────────────────────────────────────────────
                inner = tk.Frame(panel, bg=COLOURS["bg_item"])
                inner.pack(fill="both", expand=True, padx=1, pady=1)

                # Header — draggable
                hdr = tk.Frame(inner, bg=COLOURS["accent"], height=36)
                hdr.pack(fill="x")
                hdr.pack_propagate(False)
                hdr_lbl = tk.Label(
                    hdr, text=f"  📁  {_n} files  ··· drag to move",
                    bg=COLOURS["accent"], fg="#c7d2fe",
                    font=("Segoe UI", 8, "bold"),
                    cursor="fleur"
                )
                hdr_lbl.pack(side="left", fill="y", padx=4)
                hdr.configure(cursor="fleur")
                _drag = {"x": 0, "y": 0}
                def _hdr_press(e, _p=panel):
                    _drag["x"] = e.x_root - _p.winfo_x()
                    _drag["y"] = e.y_root - _p.winfo_y()
                    _cancel_close(_ps)
                def _hdr_move(e, _p=panel):
                    _cancel_close(_ps)
                    _p.geometry(f"+{e.x_root - _drag['x']}+{e.y_root - _drag['y']}")
                for _dw in (hdr, hdr_lbl):
                    _dw.bind("<ButtonPress-1>", _hdr_press)
                    _dw.bind("<B1-Motion>",     _hdr_move)

                # Scrollable canvas
                canvas = tk.Canvas(
                    inner, bg=COLOURS["bg_item"],
                    width=PANEL_W - 2, height=list_h,
                    highlightthickness=0
                )
                if _n * (ROW_H + 1) > MAX_LIST_H:
                    sb = tk.Scrollbar(inner, orient="vertical", command=canvas.yview)
                    canvas.configure(yscrollcommand=sb.set)
                    sb.pack(side="right", fill="y")

                canvas.pack(side="left", fill="both", expand=True)

                # ── Draw all rows as canvas items ────────────────────────────
                # Canvas items (rectangles + text) are raw drawing primitives.
                # They have no geometry manager and cost ~20× less to create
                # than equivalent tk.Frame/tk.Label widgets.  For 247 files
                # this turns ~1 200 widget-creation calls into a single fast
                # drawing pass with no batching needed.
                LIST_W  = PANEL_W - 2
                STRIP_W = 3
                BADGE_W = 36          # badge rectangle width
                BADGE_X = LIST_W - 6  # badge right edge x
                TEXT_X  = STRIP_W + 10  # filename left edge x

                for _i, _fp in enumerate(_files):
                    _y0 = _i * (ROW_H + 1)
                    _y1 = _y0 + ROW_H
                    _cy = (_y0 + _y1) // 2

                    # Row background
                    canvas.create_rectangle(
                        0, _y0, LIST_W, _y1,
                        fill=COLOURS["bg_item"], outline="",
                        tags=(f"row{_i}", "allrows")
                    )
                    # Left colour strip
                    _is_dir   = os.path.isdir(_fp)
                    _scol     = TYPE_COLOURS.get(
                        "folder" if _is_dir else "file", COLOURS["accent"]
                    )
                    canvas.create_rectangle(
                        0, _y0, STRIP_W, _y1,
                        fill=_scol, outline="",
                        tags=(f"strip{_i}",)
                    )
                    # Extension badge background
                    _bx1 = BADGE_X - BADGE_W
                    canvas.create_rectangle(
                        _bx1, _y0 + 8, BADGE_X, _y1 - 8,
                        fill=COLOURS["accent"], outline="",
                        tags=(f"badge{_i}",)
                    )
                    # Extension badge text
                    _raw   = "" if _is_dir else os.path.splitext(_fp)[1]
                    _ext_t = "dir" if _is_dir else (_raw[1:].lower() if _raw else "file")
                    canvas.create_text(
                        (_bx1 + BADGE_X) // 2, _cy,
                        text=_ext_t, fill="white",
                        font=("Segoe UI", 7, "bold"),
                        tags=(f"btxt{_i}",)
                    )
                    # Filename — width= clips text before it hits the badge
                    canvas.create_text(
                        TEXT_X, _cy,
                        text=os.path.basename(_fp),
                        fill=COLOURS["text"],
                        font=("Segoe UI", 8),
                        anchor="w",
                        width=_bx1 - TEXT_X - 4,
                        tags=(f"name{_i}", "allnames")
                    )
                    # Row separator line
                    canvas.create_line(
                        0, _y1, LIST_W, _y1,
                        fill=COLOURS["border"],
                        tags=(f"sep{_i}",)
                    )

                # Set scroll region to full content height
                canvas.configure(
                    scrollregion=(0, 0, LIST_W, len(_files) * (ROW_H + 1))
                )

                # ── Single-binding hover + click (no per-row bindings) ───────
                _hov_idx = [-1]   # mutable so closures can update it

                def _idx_at(e, _c=canvas):
                    """Convert mouse y to file index, accounting for scroll."""
                    return int(_c.canvasy(e.y) // (ROW_H + 1))

                def _on_motion(e, _c=canvas, _h=_hov_idx):
                    idx = _idx_at(e)
                    if idx == _h[0]:
                        return
                    if 0 <= _h[0] < _n:
                        _c.itemconfigure(f"row{_h[0]}", fill=COLOURS["bg_item"])
                    _h[0] = idx
                    if 0 <= idx < _n:
                        _c.itemconfigure(f"row{idx}", fill=COLOURS["bg_hover"])

                def _on_leave(e, _c=canvas, _h=_hov_idx):
                    if 0 <= _h[0] < _n:
                        _c.itemconfigure(f"row{_h[0]}", fill=COLOURS["bg_item"])
                    _h[0] = -1

                def _on_click(e, _c=canvas, _ps=_pst):
                    idx = _idx_at(e)
                    if 0 <= idx < _n:
                        try:
                            if _ps["win"] and _ps["win"].winfo_exists():
                                _ps["win"].destroy()
                        except Exception:
                            pass
                        _ps["win"] = None
                        _single            = dict(item)
                        _single["content"] = [_files[idx]]
                        self._paste_item(_single)

                canvas.bind("<Motion>",   _on_motion)
                canvas.bind("<Leave>",    _on_leave)
                canvas.bind("<Button-1>", _on_click)
                canvas.bind("<MouseWheel>",
                            lambda e, c=canvas: c.yview_scroll(
                                int(-1 * (e.delta / 120)), "units"))
                if self.profiles:
                    def _on_panel_rclick(e, _cc=_cancel_close):
                        # Cancel any pending close BEFORE the menu opens,
                        # because tk_popup causes a <Leave> on the canvas
                        # which would schedule a 250 ms close — making the
                        # panel and menu both disappear shortly after.
                        _cc()
                        self._show_send_to_menu(e, item)
                        # Cancel again 60 ms later in case <Leave> fires
                        # asynchronously after tk_popup returns.
                        self.root.after(60, _cc)
                    canvas.bind("<Button-3>", _on_panel_rclick)

                # Keep panel alive while mouse is inside
                panel.bind("<Enter>", lambda e: _cancel_close())
                panel.bind("<Leave>", lambda e: _schedule_close())

                panel.update_idletasks()
                panel.geometry(f"+{panel_x}+{row_y}")
                panel.deiconify()

            # Add panel open/close onto the existing hover bindings
            def _row_enter(e): _open_panel()
            def _row_leave(e): _schedule_close()

            for _w in [row, thumb_frame, text_frame, preview_label, source_label]:
                _w.bind("<Enter>", _row_enter, add="+")
                _w.bind("<Leave>", _row_leave, add="+")


    def _build_file_panel_row(self, parent, filepath, parent_item, row_w, row_h=32):
        """
        Builds one compact icon-free row inside the multi-file side panel.

        No PIL/ImageTk work at all — just plain tk widgets — so 247 rows
        build in a fraction of the time that icons would require.

        Layout (left → right, 32 px tall):
          3 px colour strip | 8 px gap | filename (expands) | ext badge |

        Badge text = raw file extension in lowercase ("jpg", "py", "pdf", …).
        Folders have no extension so they show "dir".
        Files with no extension show "file".

        Left-click  → paste just this one file.
        Right-click → Send-to-profile menu for the parent multi-file item.
        """
        is_dir = os.path.isdir(filepath)
        if is_dir:
            ext_text  = "dir"
            strip_col = TYPE_COLOURS.get("folder", COLOURS["accent"])
        else:
            raw_ext   = os.path.splitext(filepath)[1]          # e.g. ".jpg"
            ext_text  = raw_ext[1:].lower() if raw_ext else "file"
            strip_col = TYPE_COLOURS.get("file", COLOURS["accent"])

        row_bg = COLOURS["bg_item"]
        prow   = tk.Frame(parent, bg=row_bg, height=row_h, width=row_w)
        prow.pack(fill="x")
        prow.pack_propagate(False)

        # Left colour strip — 3 px at rest, 5 px on hover
        strip = tk.Frame(prow, bg=strip_col, width=3)
        strip.pack(side="left", fill="y")
        strip.pack_propagate(False)

        tk.Frame(prow, bg=row_bg, width=8).pack(side="left", fill="y")   # indent gap

        # Extension badge — packed RIGHT before the filename so it reserves space
        badge = tk.Label(
            prow, text=ext_text,
            bg=COLOURS["accent"], fg="white",
            font=("Segoe UI", 7, "bold"),
            padx=5, pady=0, width=4, anchor="center"
        )
        badge.pack(side="right", padx=(0, 6))

        # Filename — fills whatever is left
        fname    = os.path.basename(filepath)
        name_lbl = tk.Label(
            prow, text=fname,
            bg=row_bg, fg=COLOURS["text"],
            font=("Segoe UI", 8), anchor="w",
            wraplength=row_w - 75, justify="left"
        )
        name_lbl.pack(side="left", fill="x", expand=True)

        # Thin separator
        tk.Frame(parent, bg=COLOURS["border"], height=1).pack(fill="x")

        # Hover — instant colour swap + strip widen (no animation, keeps it fast)
        _hov = [prow, name_lbl]

        def _in(e):
            for w in _hov:
                try: w.configure(bg=COLOURS["bg_hover"])
                except Exception: pass
            try: strip.configure(width=5)
            except Exception: pass

        def _out(e):
            for w in _hov:
                try: w.configure(bg=row_bg)
                except Exception: pass
            try: strip.configure(width=3)
            except Exception: pass

        for w in _hov:
            w.bind("<Enter>", _in)
            w.bind("<Leave>", _out)

        # Left-click → paste this file only
        def _paste_one(e=None, fp=filepath):
            single            = dict(parent_item)
            single["content"] = [fp]
            self._paste_item(single)

        for w in _hov:
            w.bind("<Button-1>", _paste_one)

        # Right-click → Send-to-profile menu for the parent item
        if self.profiles:
            for w in _hov:
                w.bind("<Button-3>",
                       lambda e, i=parent_item: self._show_send_to_menu(e, i))


    def _show_profile_menu(self, anchor_widget):
        """
        Shows a dropdown menu of all profiles below the profile switcher label.
        Clicking a profile switches to it and refreshes the popup.
        """
        menu = tk.Menu(self.window, tearoff=0,
                       bg=COLOURS["bg_item"], fg=COLOURS["text"],
                       activebackground=COLOURS["accent"],
                       activeforeground="white",
                       relief="flat", bd=0)

        for profile in self.profiles.get_all_profiles():
            pid   = profile["id"]
            name  = profile["name"]
            count = self.profiles.get_profile_item_count(pid)
            label = f"{'✔  ' if pid == self.profiles.active_id else '    '}{name}  ({count})"
            menu.add_command(
                label=label,
                command=lambda p=pid: self._switch_profile(p)
            )

        # Position the menu directly below the label
        x = anchor_widget.winfo_rootx()
        y = anchor_widget.winfo_rooty() + anchor_widget.winfo_height()
        menu.tk_popup(x, y)


    def _switch_profile(self, profile_id):
        """Switches the active profile and rebuilds the popup."""
        self.profiles.set_active(profile_id)

        # Detect empty profile before rebuilding
        chosen = self.profiles.get_active_profile()
        is_empty = not self.profiles.get_active_items() and not chosen.get("built_in")
        if is_empty:
            self.profiles.set_active("general")

        if self.window:
            x = self.window.winfo_x()
            y = self.window.winfo_y()
            self._build_and_show(x, y)

        # Show toast AFTER popup is rebuilt so we can lift it on top
        if is_empty:
            self._show_toast("Selected profile empty")


    def _show_send_to_menu(self, event, item):
        """
        Shows a right-click context menu on an item with a
        'Send to profile' submenu listing all user profiles.
        Items already in a profile are shown with a checkmark.
        Clicking a profile adds (or removes) the item from it.
        """
        user_profiles = [p for p in self.profiles.get_all_profiles()
                         if not p.get("built_in")]

        if not user_profiles:
            # No user profiles yet — show a hint instead
            menu = tk.Menu(self.window, tearoff=0,
                           bg=COLOURS["bg_item"], fg=COLOURS["text_dim"],
                           relief="flat", bd=0)
            menu.add_command(label="No profiles yet — create one in Settings",
                             state="disabled")
            menu.tk_popup(event.x_root, event.y_root)
            return

        menu = tk.Menu(self.window, tearoff=0,
                       bg=COLOURS["bg_item"], fg=COLOURS["text"],
                       activebackground=COLOURS["accent"],
                       activeforeground="white",
                       relief="flat", bd=0)

        menu.add_command(label="Send to profile:", state="disabled",
                         font=("Segoe UI", 8))
        menu.add_separator()

        item_profiles = set(self.profiles.get_item_profiles(item["id"]))

        for profile in user_profiles:
            pid   = profile["id"]
            check = "✔  " if pid in item_profiles else "    "
            menu.add_command(
                label=f"{check}{profile['name']}",
                command=lambda p=pid: self._toggle_item_in_profile(item, p)
            )

        menu.tk_popup(event.x_root, event.y_root)


    def _toggle_item_in_profile(self, item, profile_id):
        """Adds item to profile if not there, removes it if already there."""
        item_profiles = set(self.profiles.get_item_profiles(item["id"]))
        if profile_id in item_profiles:
            self.profiles.remove_item_from_profile(item["id"], profile_id)
        else:
            self.profiles.add_item_to_profile(item["id"], profile_id)
        self._refresh()


    def _make_draggable(self, widget):
        """
        Makes the popup window draggable by the given widget.
        Bind this to the header bar and its child labels so the user
        can reposition the popup by dragging from the title area.
        The cursor changes to a move icon to hint that dragging is possible.
        """
        widget.configure(cursor="fleur")
        widget.bind("<Button-1>",  self._on_drag_start)
        widget.bind("<B1-Motion>", self._on_drag_motion)


    def _on_drag_start(self, event):
        """Records the offset of the click relative to the window's top-left."""
        self._drag_x = event.x_root - self.window.winfo_x()
        self._drag_y = event.y_root - self.window.winfo_y()


    def _on_drag_motion(self, event):
        """Moves the window to follow the mouse during a drag."""
        new_x = event.x_root - self._drag_x
        new_y = event.y_root - self._drag_y
        self.window.geometry(f"+{new_x}+{new_y}")


    def _build_thumbnail(self, parent, item, bg):
        """
        Shows a thumbnail or type icon for the clipboard item.

        Priority order:
          1. Image data item     → real PIL thumbnail
          2. Folder(s)           → folder icon
          3. Image file(s)       → real PIL thumbnail (single) or image icon
          4. Any known extension → specific icon (video/audio/excel/word/…)
          5. Unknown extension   → generic amber file icon
        """
        # ── Copied image data (not a file path) ────────────────────────────
        if item["type"] == "image":
            try:
                img = Image.open(item["content"])
                img.thumbnail((THUMB_SIZE, THUMB_SIZE))
                photo = ImageTk.PhotoImage(img)
                self.thumbnails.append(photo)
                tk.Label(parent, image=photo, bg=bg).pack(expand=True)
                return
            except Exception:
                pass  # fall through to generic image icon

        icon_type = item["type"]   # default: "text", "url", "code", "bash", "image"

        # ── Copied file(s) ──────────────────────────────────────────────────
        if icon_type == "file":
            files = item.get("content", [])
            if isinstance(files, list) and files:
                if all(os.path.isdir(f) for f in files):
                    icon_type = "folder"
                else:
                    # Classify by the extension of the first file
                    ext = os.path.splitext(files[0])[1].lower()
                    icon_type = _FILE_TYPE_MAP.get(ext, "file")

                    # Single image file → show a real thumbnail
                    if icon_type == "image" and len(files) == 1:
                        try:
                            img = Image.open(files[0])
                            img.thumbnail((THUMB_SIZE, THUMB_SIZE))
                            photo = ImageTk.PhotoImage(img)
                            self.thumbnails.append(photo)
                            tk.Label(parent, image=photo, bg=bg).pack(expand=True)
                            return
                        except Exception:
                            pass  # fall through to image icon

        icon_img = self._draw_type_icon(icon_type, THUMB_SIZE)
        photo = ImageTk.PhotoImage(icon_img)
        self.thumbnails.append(photo)
        tk.Label(parent, image=photo, bg=bg).pack(expand=True)


    def _draw_type_icon(self, icon_type, size):
        """
        Draws a colorful type icon as a PIL RGBA image.

        text   → white document with indigo text lines
        url    → chain-link PNG loaded from assets/
        file   → amber file with folded corner
        folder → yellow Windows-style folder
        image  → teal frame with mountain scene (fallback)

        Results are cached by (icon_type, size) on the class so that building
        a panel with 100 files of the same type only draws once.
        """
        _key = (icon_type, size)
        if _key in DropdownPopup._icon_cache:
            return DropdownPopup._icon_cache[_key]

        img = Image.new("RGBA", (size, size), (0, 0, 0, 0))
        d   = ImageDraw.Draw(img)

        if icon_type == "text":
            # White paper body
            d.rounded_rectangle([2, 1, size - 4, size - 1], radius=3, fill="#ffffff")
            # Top-right folded corner
            fold = 8
            d.polygon([(size - fold - 2, 1), (size - 4, fold),
                        (size - fold - 2, fold)], fill="#c7d2fe")
            # Indigo text lines
            line_color = "#4f46e5"
            for y in [10, 15, 20, 25]:
                end_x = size - 12 if y == 20 else size - 8
                d.rectangle([6, y, end_x, y + 2], fill=line_color)

        elif icon_type == "url":
            # Chain-link icon — two interlocking horizontal pill/capsule rings.
            # Lower-right ring drawn first (behind); upper-left ring drawn second (in front).
            d.rounded_rectangle([1, 1, size - 1, size - 1], radius=6, fill="#0ea5e9")
            lw = 3   # ring wall thickness
            # Lower-right link (behind)
            d.rounded_rectangle([13, 15, size - 2, size - 5], radius=5, fill="white")
            d.rounded_rectangle([13 + lw, 15 + lw, size - 2 - lw, size - 5 - lw],
                                 radius=3, fill="#0ea5e9")
            # Upper-left link (in front — drawn on top, so it overlaps in the middle)
            d.rounded_rectangle([2, 5, 22, 19], radius=5, fill="white")
            d.rounded_rectangle([2 + lw, 5 + lw, 22 - lw, 19 - lw],
                                 radius=3, fill="#0ea5e9")

        elif icon_type == "html":
            # Globe — web-page / HTML file icon (same globe used by URL before)
            cx, cy = size // 2, size // 2
            r = size // 2 - 2
            d.ellipse([cx - r, cy - r, cx + r, cy + r], fill="#0ea5e9")
            d.ellipse([cx - r, cy - r, cx + r, cy + r], outline="#bae6fd", width=1)
            d.line([cx - r, cy, cx + r, cy], fill="#bae6fd", width=1)
            d.line([cx, cy - r, cx, cy + r], fill="#bae6fd", width=1)
            rh = r // 2
            d.arc([cx - rh, cy - r, cx + rh, cy + r], 0, 360, fill="#bae6fd", width=1)

        elif icon_type == "video":
            # Dark indigo background + red circle + white play triangle ►
            d.rounded_rectangle([1, 1, size - 1, size - 1], radius=5, fill="#1e1b4b")
            cx, cy = size // 2, size // 2
            r = size // 2 - 5
            d.ellipse([cx - r, cy - r, cx + r, cy + r], fill="#ef4444")
            tx = cx - r // 3 + 1
            d.polygon([
                (tx,         cy - r // 2 - 1),
                (cx + r // 2 + 2, cy),
                (tx,         cy + r // 2 + 1),
            ], fill="white")

        elif icon_type == "audio":
            # Purple background + eighth-note music symbol
            d.rounded_rectangle([1, 1, size - 1, size - 1], radius=5, fill="#7c3aed")
            hx, hy = size // 2 - 3, size // 2 + 6   # note-head centre
            # Oval note head
            d.ellipse([hx - 5, hy - 3, hx + 5, hy + 4], fill="white")
            # Vertical stem (right side of head, going up)
            sx = hx + 5
            d.rectangle([sx - 1, hy - 3 - 12, sx + 1, hy - 3], fill="white")
            # Flag (two-line curve at stem top)
            d.line([(sx, hy - 15), (sx + 7, hy - 10), (sx + 5, hy - 5)],
                   fill="white", width=2)

        elif icon_type == "excel":
            # Microsoft-Excel green + white spreadsheet grid
            d.rounded_rectangle([1, 1, size - 1, size - 1], radius=5, fill="#217346")
            m = 5   # margin
            # 4 horizontal lines → 3 rows
            row_h = (size - 2 * m) // 3
            for i in range(4):
                y = m + i * row_h
                d.rectangle([m, y, size - m, y + 1], fill="white")
            # 1 vertical divider → 2 columns
            mid = size // 2
            d.rectangle([mid, m, mid + 1, size - m], fill="white")

        elif icon_type == "word":
            # Microsoft-Word blue + white document with text lines
            d.rounded_rectangle([1, 1, size - 1, size - 1], radius=5, fill="#2b579a")
            # Document body
            d.rounded_rectangle([5, 4, size - 5, size - 4], radius=2, fill="#d6e4f7")
            # Text lines inside document
            for yl in [10, 15, 20, 25]:
                x2 = size - 12 if yl == 20 else size - 8
                d.rectangle([8, yl, x2, yl + 2], fill="#2b579a")

        elif icon_type == "ppt":
            # PowerPoint orange-red + slide shape with title bar + speaker stand
            d.rounded_rectangle([1, 1, size - 1, size - 1], radius=5, fill="#c43e1c")
            # Slide white rectangle
            d.rounded_rectangle([4, 6, size - 4, size - 9], radius=2, fill="white")
            # Title bar inside slide
            d.rectangle([7, 9, size - 7, 13], fill="#c43e1c")
            # Content lines
            d.rectangle([7, 16, size - 10, 18], fill="#e8a090")
            d.rectangle([7, 21, size - 13, 23], fill="#e8a090")
            # Small speaker-stand triangle at bottom
            cx = size // 2
            d.polygon([(cx - 3, size - 9), (cx + 3, size - 9), (cx, size - 4)],
                      fill="white")

        elif icon_type == "pdf":
            # Red background + amber-tinted document with decreasing content bars
            d.rounded_rectangle([1, 1, size - 1, size - 1], radius=5, fill="#cc1c1c")
            fold = 7
            # Document body
            d.polygon([
                (5, 3), (size - fold - 3, 3),
                (size - 3, fold + 2), (size - 3, size - 3),
                (5, size - 3)
            ], fill="white")
            # Fold shadow triangle
            d.polygon([
                (size - fold - 3, 3), (size - 3, fold + 2),
                (size - fold - 3, fold + 2)
            ], fill="#e87070")
            # Three red content bars (decreasing width — suggests "PDF" content)
            for i, x2 in enumerate([size - 7, size - 10, size - 14]):
                d.rectangle([9, 14 + i * 5, x2, 16 + i * 5], fill="#cc1c1c")

        elif icon_type == "exe":
            # Dark gray background + white gear/cog
            import math
            d.rounded_rectangle([1, 1, size - 1, size - 1], radius=5, fill="#374151")
            cx, cy = size // 2, size // 2
            R_outer, R_inner, R_hole = 13, 10, 4
            # Draw gear as outer circle, then subtract teeth effect with dark dots
            d.ellipse([cx - R_outer, cy - R_outer, cx + R_outer, cy + R_outer],
                      fill="white")
            d.ellipse([cx - R_inner, cy - R_inner, cx + R_inner, cy + R_inner],
                      fill="#374151")
            # 8 teeth around the perimeter
            for deg in range(0, 360, 45):
                a = math.radians(deg)
                tx = int(cx + (R_outer - 1) * math.cos(a))
                ty = int(cy + (R_outer - 1) * math.sin(a))
                d.ellipse([tx - 3, ty - 3, tx + 3, ty + 3], fill="white")
            # Re-draw inner ring and hole
            d.ellipse([cx - R_inner + 1, cy - R_inner + 1,
                       cx + R_inner - 1, cy + R_inner - 1], fill="white")
            d.ellipse([cx - R_hole, cy - R_hole, cx + R_hole, cy + R_hole],
                      fill="#374151")

        elif icon_type == "zip":
            # Mid-gray background + white box with zipper stripes
            d.rounded_rectangle([1, 1, size - 1, size - 1], radius=5, fill="#6b7280")
            # Box lid
            d.rounded_rectangle([4, 5, size - 4, 13], radius=2, fill="#d1d5db")
            # Box body
            d.rounded_rectangle([4, 12, size - 4, size - 4], radius=2, fill="white")
            # Zipper strip down the centre of the box
            cx = size // 2
            d.rectangle([cx - 2, 5, cx + 2, size - 4], fill="#9ca3af")
            # Zipper teeth (alternating notches)
            for zy in range(7, size - 5, 4):
                d.rectangle([cx - 4, zy, cx - 2, zy + 2], fill="#d1d5db")
                d.rectangle([cx + 2, zy + 2, cx + 4, zy + 4], fill="#d1d5db")

        elif icon_type == "file":
            # Amber file with folded corner — no stripes (stripes = text only)
            fold = 9
            d.polygon([
                (4, 2), (size - fold - 2, 2),
                (size - 3, fold + 1), (size - 3, size - 2),
                (4, size - 2)
            ], fill="#f59e0b")
            # Fold shadow triangle
            d.polygon([
                (size - fold - 2, 2), (size - 3, fold + 1),
                (size - fold - 2, fold + 1)
            ], fill="#b45309")

        elif icon_type == "folder":
            # Yellow Windows-style folder
            d.rounded_rectangle([2, 8, 14, 14], radius=2, fill="#fbbf24")
            d.rounded_rectangle([2, 12, size - 2, size - 3], radius=3, fill="#f59e0b")
            d.rounded_rectangle([2, 12, size - 2, 17], radius=3, fill="#fde68a")

        elif icon_type == "code":
            # Dark purple background with </> in white
            d.rounded_rectangle([1, 1, size - 1, size - 1], radius=5, fill="#6d28d9")
            # Draw < / > symbol using lines
            cx, cy = size // 2, size // 2
            # "<" — two lines meeting at a point on the left
            d.line([cx - 9, cy - 5, cx - 14, cy,  ], fill="white", width=2)
            d.line([cx - 14, cy,    cx - 9, cy + 5], fill="white", width=2)
            # "/" — diagonal line in centre
            d.line([cx - 2, cy + 7, cx + 2, cy - 7], fill="#a78bfa", width=2)
            # ">" — two lines meeting at a point on the right
            d.line([cx + 9, cy - 5, cx + 14, cy   ], fill="white", width=2)
            d.line([cx + 14, cy,    cx + 9, cy + 5], fill="white", width=2)

        elif icon_type == "bash":
            d.rounded_rectangle([1, 1, size - 1, size - 1], radius=4, fill="#0d1117")
            d.rounded_rectangle([1, 1, size - 1, 9], radius=4, fill="#161b22")
            d.ellipse([ 4, 3,  8, 7], fill="#ff5f56")
            d.ellipse([10, 3, 14, 7], fill="#febc2e")
            d.ellipse([16, 3, 20, 7], fill="#28c840")
            cx = 6
            cy = size // 2 + 4
            d.line([cx,     cy - 4, cx + 5, cy    ], fill="#4ade80", width=2)
            d.line([cx + 5, cy,     cx,     cy + 4], fill="#4ade80", width=2)
            d.rectangle([cx + 8, cy + 2, cx + 18, cy + 4], fill="#4ade80")

        elif icon_type == "url":
            # Chain-link: two interlocking pill rings (lower-right behind, upper-left in front)
            d.rounded_rectangle([1, 1, size - 1, size - 1], radius=6, fill="#0ea5e9")
            lw = 3
            d.rounded_rectangle([13, 15, size - 2, size - 5], radius=5, fill="white")
            d.rounded_rectangle([13 + lw, 15 + lw, size - 2 - lw, size - 5 - lw], radius=3, fill="#0ea5e9")
            d.rounded_rectangle([2, 5, 22, 19], radius=5, fill="white")
            d.rounded_rectangle([2 + lw, 5 + lw, 22 - lw, 19 - lw], radius=3, fill="#0ea5e9")

        elif icon_type == "html":
            cx, cy = size // 2, size // 2
            r = size // 2 - 2
            d.ellipse([cx - r, cy - r, cx + r, cy + r], fill="#0ea5e9")
            d.ellipse([cx - r, cy - r, cx + r, cy + r], outline="#bae6fd", width=1)
            d.line([cx - r, cy, cx + r, cy], fill="#bae6fd", width=1)
            d.line([cx, cy - r, cx, cy + r], fill="#bae6fd", width=1)
            rh = r // 2
            d.arc([cx - rh, cy - r, cx + rh, cy + r], 0, 360, fill="#bae6fd", width=1)

        elif icon_type == "video":
            d.rounded_rectangle([1, 1, size - 1, size - 1], radius=5, fill="#1e1b4b")
            cx, cy = size // 2, size // 2
            r = size // 2 - 5
            d.ellipse([cx - r, cy - r, cx + r, cy + r], fill="#ef4444")
            tx = cx - r // 3 + 1
            d.polygon([(tx, cy - r // 2 - 1), (cx + r // 2 + 2, cy), (tx, cy + r // 2 + 1)], fill="white")

        elif icon_type == "audio":
            d.rounded_rectangle([1, 1, size - 1, size - 1], radius=5, fill="#7c3aed")
            hx, hy = size // 2 - 3, size // 2 + 6
            d.ellipse([hx - 5, hy - 3, hx + 5, hy + 4], fill="white")
            sx = hx + 5
            d.rectangle([sx - 1, hy - 3 - 12, sx + 1, hy - 3], fill="white")
            d.line([(sx, hy - 15), (sx + 7, hy - 10), (sx + 5, hy - 5)], fill="white", width=2)

        elif icon_type == "excel":
            d.rounded_rectangle([1, 1, size - 1, size - 1], radius=5, fill="#217346")
            m = 5
            row_h = (size - 2 * m) // 3
            for i in range(4):
                y = m + i * row_h
                d.rectangle([m, y, size - m, y + 1], fill="white")
            mid = size // 2
            d.rectangle([mid, m, mid + 1, size - m], fill="white")

        elif icon_type == "word":
            d.rounded_rectangle([1, 1, size - 1, size - 1], radius=5, fill="#2b579a")
            d.rounded_rectangle([5, 4, size - 5, size - 4], radius=2, fill="#d6e4f7")
            for yl in [10, 15, 20, 25]:
                x2 = size - 12 if yl == 20 else size - 8
                d.rectangle([8, yl, x2, yl + 2], fill="#2b579a")

        elif icon_type == "ppt":
            d.rounded_rectangle([1, 1, size - 1, size - 1], radius=5, fill="#c43e1c")
            d.rounded_rectangle([4, 6, size - 4, size - 9], radius=2, fill="white")
            d.rectangle([7, 9, size - 7, 13], fill="#c43e1c")
            d.rectangle([7, 16, size - 10, 18], fill="#e8a090")
            d.rectangle([7, 21, size - 13, 23], fill="#e8a090")
            cx = size // 2
            d.polygon([(cx - 3, size - 9), (cx + 3, size - 9), (cx, size - 4)], fill="white")

        elif icon_type == "pdf":
            d.rounded_rectangle([1, 1, size - 1, size - 1], radius=5, fill="#cc1c1c")
            fold = 7
            d.polygon([
                (5, 3), (size - fold - 3, 3),
                (size - 3, fold + 2), (size - 3, size - 3),
                (5, size - 3)
            ], fill="white")
            d.polygon([(size - fold - 3, 3), (size - 3, fold + 2), (size - fold - 3, fold + 2)], fill="#e87070")
            for i, x2 in enumerate([size - 7, size - 10, size - 14]):
                d.rectangle([9, 14 + i * 5, x2, 16 + i * 5], fill="#cc1c1c")

        elif icon_type == "exe":
            import math as _math
            d.rounded_rectangle([1, 1, size - 1, size - 1], radius=5, fill="#374151")
            cx, cy = size // 2, size // 2
            R_outer, R_inner, R_hole = 13, 10, 4
            d.ellipse([cx - R_outer, cy - R_outer, cx + R_outer, cy + R_outer], fill="white")
            d.ellipse([cx - R_inner, cy - R_inner, cx + R_inner, cy + R_inner], fill="#374151")
            for deg in range(0, 360, 45):
                a = _math.radians(deg)
                tx = int(cx + (R_outer - 1) * _math.cos(a))
                ty = int(cy + (R_outer - 1) * _math.sin(a))
                d.ellipse([tx - 3, ty - 3, tx + 3, ty + 3], fill="white")
            d.ellipse([cx - R_inner + 1, cy - R_inner + 1, cx + R_inner - 1, cy + R_inner - 1], fill="white")
            d.ellipse([cx - R_hole, cy - R_hole, cx + R_hole, cy + R_hole], fill="#374151")

        elif icon_type == "zip":
            d.rounded_rectangle([1, 1, size - 1, size - 1], radius=5, fill="#6b7280")
            d.rounded_rectangle([4, 5, size - 4, 13], radius=2, fill="#d1d5db")
            d.rounded_rectangle([4, 12, size - 4, size - 4], radius=2, fill="white")
            cx = size // 2
            d.rectangle([cx - 2, 5, cx + 2, size - 4], fill="#9ca3af")
            for zy in range(7, size - 5, 4):
                d.rectangle([cx - 4, zy, cx - 2, zy + 2], fill="#d1d5db")
                d.rectangle([cx + 2, zy + 2, cx + 4, zy + 4], fill="#d1d5db")

        else:
            # Fallback: teal image/unknown icon
            d.rounded_rectangle([2, 2, size - 2, size - 2], radius=4, fill="#0891b2")
            d.ellipse([7, 6, 14, 13], fill="#fef9c3")
            d.polygon([(4, size - 6), (size // 2, 14), (size - 4, size - 6)], fill="#164e63")

        DropdownPopup._icon_cache[_key] = img
        return img


    def _make_button(self, parent, text, command, colour):
        """Creates a small styled action button."""
        btn = tk.Label(
            parent, text=text,
            bg=COLOURS["bg_item"], fg=colour,
            font=("Segoe UI", 9),
            padx=4, pady=2, cursor="hand2"
        )
        btn.pack(side="top", pady=1)
        btn.bind("<Button-1>", lambda e, c=command: (c(), "break")[1])
        btn.bind("<Enter>", lambda e: btn.configure(bg=COLOURS["bg_hover"]))
        btn.bind("<Leave>", lambda e: btn.configure(bg=COLOURS["bg_item"]))


    # ============================================================
    # ACTIONS
    # ============================================================

    def _on_item_press(self, event, item):
        """Records the press position so we can detect drag vs click."""
        self._drag_item    = item
        self._drag_start_x = event.x_root
        self._drag_start_y = event.y_root
        self._is_dragging  = False


    def _on_item_drag(self, event, item):
        if not self._is_dragging:
            dx = abs(event.x_root - self._drag_start_x)
            dy = abs(event.y_root - self._drag_start_y)
            if dx > DRAG_THRESHOLD or dy > DRAG_THRESHOLD:
                self._is_dragging = True
                self._drag_ghost  = self._create_drag_ghost(item)
        if self._is_dragging and self._drag_ghost:
            self._drag_ghost.geometry(f"+{event.x_root + 14}+{event.y_root + 14}")


    def _on_item_release(self, event, item):
        if self._is_dragging:
            drop_x, drop_y = event.x_root, event.y_root
            if self._drag_ghost:
                self._drag_ghost.destroy()
                self._drag_ghost = None
            self._is_dragging = False
            self._drag_item   = None
            self.hide()
            self.root.after(150, lambda: self._do_drop(item, drop_x, drop_y))
        else:
            self._paste_item(item)


    def _create_drag_ghost(self, item):
        ghost = tk.Toplevel(self.root)
        ghost.overrideredirect(True)
        ghost.attributes("-topmost", True)
        ghost.attributes("-alpha", 0.85)
        ghost.configure(bg=COLOURS["accent"])
        icon    = "📄" if item["type"] == "text" else ("🖼️" if item["type"] == "image" else "📁")
        preview = self.history.get_preview(item)
        tk.Label(ghost, text=f"{icon}  {preview[:40]}", bg=COLOURS["accent"], fg="white",
                 font=("Segoe UI", 9, "bold"), padx=10, pady=5).pack()
        x, y = pyautogui.position()
        ghost.geometry(f"+{x + 14}+{y + 14}")
        ghost.deiconify()
        return ghost


    def _do_drop(self, item, x, y):
        try:
            pyautogui.click(x, y)
            time.sleep(0.1)
        except Exception as e:
            print(f"Drop click error: {e}")
        self._do_paste(item)


    def _paste_item(self, item):
        """Hides popup, restores item to clipboard, simulates Ctrl+V."""
        self.hide()
        self.root.after(250, lambda: self._do_paste(item))


    def _do_paste(self, item):
        """Actually performs the paste operation."""
        import struct, hashlib
        if self.watcher:
            self.watcher.paused = True
        try:
            win32clipboard.OpenClipboard()
            win32clipboard.EmptyClipboard()
            if item["type"] in ("text", "url", "code", "bash"):
                win32clipboard.SetClipboardData(win32con.CF_UNICODETEXT, item["content"])
                if self.watcher:
                    self.watcher.last_seen = hashlib.md5(
                        item["content"].encode("utf-8", errors="ignore")
                    ).hexdigest()
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
                            str(files).encode("utf-8", errors="ignore")
                        ).hexdigest()
            elif item["type"] == "image":
                img = Image.open(item["content"])
                output = io.BytesIO()
                img.convert("RGB").save(output, "BMP")
                data = output.getvalue()[14:]
                output.close()
                win32clipboard.SetClipboardData(win32con.CF_DIB, data)
            win32clipboard.CloseClipboard()
        except Exception as e:
            print(f"Paste error: {e}")
            try:
                win32clipboard.CloseClipboard()
            except Exception:
                pass
            if self.watcher:
                self.watcher.paused = False
            return
        # For most apps: WS_EX_NOACTIVATE kept the original app focused
        # throughout, so Ctrl+V lands there with no extra work.
        #
        # Desktop exception: the registry-trigger path (right-click desktop
        # → Paste from ClipDrop) spawns a short-lived pythonw.exe that can
        # shift focus away from the desktop shell before our popup appears.
        # We fix this ONLY for desktop windows — SetForegroundWindow succeeds
        # here because the user's click on our popup just gave ClipDrop a
        # recent input event, which Windows requires before allowing the call.
        _target = getattr(self, "_paste_target", None)
        self._paste_target = None
        if _target:
            try:
                import win32gui as _wg
                _cls = _wg.GetClassName(_target)
                if _cls in ("Progman", "WorkerW"):
                    # Resolve top-level desktop window → focusable SysListView32
                    _sv = _wg.FindWindowEx(_target, None, "SHELLDLL_DefView", None)
                    if _sv:
                        _lv = _wg.FindWindowEx(_sv, None, "SysListView32", None)
                        if _lv:
                            _target = _lv
                    _wg.SetForegroundWindow(_target)
                    _wg.BringWindowToTop(_target)
                    time.sleep(0.1)
            except Exception:
                pass
        pyautogui.hotkey("ctrl", "v")
        if self.watcher:
            time.sleep(0.5)
            self.watcher.paused = False


    def _toggle_pin(self, item):
        self.history.toggle_pin(item["id"])
        self._refresh()

    def _delete_item(self, item):
        if self.profiles:
            self.profiles.remove_item_from_all(item["id"])
        self.history.delete_item(item["id"])
        self._refresh()

    def _move_up(self, item):
        self.history.move_up(item["id"])
        self._refresh()

    def _move_down(self, item):
        self.history.move_down(item["id"])
        self._refresh()

    def _refresh(self):
        """Rebuilds the popup at the same position after any change."""
        if self.window:
            x = self.window.winfo_x()
            y = self.window.winfo_y()
            self._build_and_show(x, y)


    # ============================================================
    # HELPERS
    # ============================================================

    def _on_focus_out(self, event):
        """Hide popup when user clicks outside it."""
        self.root.after(150, self._check_focus)

    def _check_focus(self):
        """
        Confirm focus truly left the application before hiding.

        Uses root.focus_displayof() instead of window.focus_get() so that
        any window belonging to this Tk instance keeps the popup alive —
        including the side panel, its scrollbar, and any send-to menu.

        window.focus_get() only checked widgets inside the main popup window,
        so clicking the side-panel scrollbar returned None and incorrectly
        closed the popup.
        """
        try:
            if self.root.focus_displayof() is None:
                self.hide()
        except Exception:
            self.hide()

    def _position_popup(self, x, y):
        """Positions popup at cursor, keeping it fully on screen."""
        popup_w  = self.window.winfo_reqwidth()
        popup_h  = self.window.winfo_reqheight()
        screen_w = self.window.winfo_screenwidth()
        screen_h = self.window.winfo_screenheight()
        if x + popup_w > screen_w:
            x = screen_w - popup_w - 10
        if y + popup_h > screen_h:
            y = screen_h - popup_h - 10
        self.window.geometry(f"+{x}+{y}")
