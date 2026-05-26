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
    "bg_hover":     "#3a3a5e",
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


class DropdownPopup:

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

        # Hide until fully built to prevent flicker
        self.window.withdraw()

        # Close when focus is lost
        self.window.bind("<FocusOut>", self._on_focus_out)
        self.window.bind("<Escape>",   lambda e: self.hide())

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
        self.window.focus_force()
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
            # Left type-strip grows 3 px → 5 px
            try:
                strip.configure(width=max(3, int(3 + 2 * t)))
            except Exception:
                pass
            # Bottom separator glows from border colour → type colour (capped at 70 %)
            sep_col = DropdownPopup._hex_lerp(COLOURS["border"], type_strip_colour, t * 0.7)
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
            _anim["t"] += diff * 0.32  # Ease-out: cover 32 % of remaining gap per frame
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
        """Shows image thumbnail or a colorful PIL-drawn type icon."""
        if item["type"] == "image":
            try:
                img = Image.open(item["content"])
                img.thumbnail((THUMB_SIZE, THUMB_SIZE))
                photo = ImageTk.PhotoImage(img)
                self.thumbnails.append(photo)
                tk.Label(parent, image=photo, bg=bg).pack(expand=True)
                return
            except Exception:
                pass

        # Determine icon type — detect folder vs file from path
        icon_type = item["type"]
        if icon_type == "file":
            files = item.get("content", [])
            if isinstance(files, list) and files and all(
                    os.path.isdir(f) for f in files):
                icon_type = "folder"

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
        """
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
            # Sky-blue globe with equator, meridian, and oval arc
            cx, cy = size // 2, size // 2
            r = size // 2 - 2
            d.ellipse([cx - r, cy - r, cx + r, cy + r], fill="#0ea5e9")
            d.ellipse([cx - r, cy - r, cx + r, cy + r], outline="#bae6fd", width=1)
            d.line([cx - r, cy, cx + r, cy], fill="#bae6fd", width=1)
            d.line([cx, cy - r, cx, cy + r], fill="#bae6fd", width=1)
            rh = r // 2
            d.arc([cx - rh, cy - r, cx + rh, cy + r], 0, 360, fill="#bae6fd", width=1)

        elif icon_type == "file":
            # Amber file with folded corner
            fold = 9
            d.polygon([
                (4, 2), (size - fold - 2, 2),
                (size - 3, fold + 1), (size - 3, size - 2),
                (4, size - 2)
            ], fill="#f59e0b")
            # Fold shadow
            d.polygon([
                (size - fold - 2, 2), (size - 3, fold + 1),
                (size - fold - 2, fold + 1)
            ], fill="#b45309")
            # Content lines
            for y in [14, 19, 24]:
                d.rectangle([8, y, size - 7, y + 2], fill="#fef3c7")

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
            # Terminal window — dark body with title bar and >_ prompt
            # Window body (near-black)
            d.rounded_rectangle([1, 1, size - 1, size - 1], radius=4, fill="#0d1117")
            # Title bar (dark grey strip at top)
            d.rounded_rectangle([1, 1, size - 1, 9], radius=4, fill="#161b22")
            # Three window-control dots in the title bar
            d.ellipse([ 4, 3,  8, 7], fill="#ff5f56")   # red   (close)
            d.ellipse([10, 3, 14, 7], fill="#febc2e")   # yellow (minimise)
            d.ellipse([16, 3, 20, 7], fill="#28c840")   # green  (maximise)
            # Prompt:  >  _
            cx = 6
            cy = size // 2 + 4
            # ">" chevron
            d.line([cx,     cy - 4, cx + 5, cy    ], fill="#4ade80", width=2)
            d.line([cx + 5, cy,     cx,     cy + 4], fill="#4ade80", width=2)
            # "_" blinking cursor block (slightly offset right of the chevron)
            d.rectangle([cx + 8, cy + 2, cx + 18, cy + 4], fill="#4ade80")

        else:
            # Fallback: teal image/unknown icon
            d.rounded_rectangle([2, 2, size - 2, size - 2], radius=4, fill="#0891b2")
            d.ellipse([7, 6, 14, 13], fill="#fef9c3")
            d.polygon([(4, size - 6), (size // 2, 14), (size - 4, size - 6)],
                      fill="#164e63")

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
        # Return "break" so the click does not propagate up to the item row
        # (which would accidentally trigger a paste alongside the button action)
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
        """
        Called while the mouse moves with button held.
        Once the cursor travels more than DRAG_THRESHOLD pixels, drag mode
        activates and a ghost preview window follows the cursor.
        """
        if not self._is_dragging:
            dx = abs(event.x_root - self._drag_start_x)
            dy = abs(event.y_root - self._drag_start_y)
            if dx > DRAG_THRESHOLD or dy > DRAG_THRESHOLD:
                self._is_dragging = True
                self._drag_ghost  = self._create_drag_ghost(item)

        if self._is_dragging and self._drag_ghost:
            # Ghost follows cursor with a small offset so the cursor stays visible
            self._drag_ghost.geometry(
                f"+{event.x_root + 14}+{event.y_root + 14}"
            )


    def _on_item_release(self, event, item):
        """
        Mouse button released.
        Short movement = click → paste into currently active window.
        Long movement  = drag → drop at the release position.
        """
        if self._is_dragging:
            drop_x, drop_y = event.x_root, event.y_root

            if self._drag_ghost:
                self._drag_ghost.destroy()
                self._drag_ghost = None
            self._is_dragging = False
            self._drag_item   = None

            # Hide the popup first, then perform the drop after a short delay
            # so the popup is fully gone before we click the target
            self.hide()
            self.root.after(150, lambda: self._do_drop(item, drop_x, drop_y))
        else:
            # Simple click — paste into the currently focused app
            self._paste_item(item)


    def _create_drag_ghost(self, item):
        """
        Creates a small semi-transparent preview window that follows the
        cursor while the user is dragging an item.
        """
        ghost = tk.Toplevel(self.root)
        ghost.overrideredirect(True)
        ghost.attributes("-topmost", True)
        ghost.attributes("-alpha", 0.85)
        ghost.configure(bg=COLOURS["accent"])

        icon    = "📄" if item["type"] == "text" else (
                  "🖼️" if item["type"] == "image" else "📁")
        preview = self.history.get_preview(item)

        tk.Label(
            ghost,
            text=f"{icon}  {preview[:40]}",
            bg=COLOURS["accent"], fg="white",
            font=("Segoe UI", 9, "bold"),
            padx=10, pady=5
        ).pack()

        x, y = pyautogui.position()
        ghost.geometry(f"+{x + 14}+{y + 14}")
        ghost.deiconify()
        return ghost


    def _do_drop(self, item, x, y):
        """
        Performs the drop at screen position (x, y).

        Clicks at the drop point to:
          - Focus the target window
          - Place the text cursor at that exact position (for text editors/fields)

        Then puts the item in the clipboard and simulates Ctrl+V to paste.
        This gives the user drag-to-drop behaviour using the same reliable
        clipboard + paste mechanism as a normal ClipDrop paste.
        """
        try:
            pyautogui.click(x, y)
            time.sleep(0.1)
        except Exception as e:
            print(f"Drop click error: {e}")

        # Reuse the existing paste logic — handles text, files, and images
        self._do_paste(item)


    def _paste_item(self, item):
        """Hides popup, restores item to clipboard, simulates Ctrl+V."""
        self.hide()
        self.root.after(150, lambda: self._do_paste(item))


    def _do_paste(self, item):
        """Actually performs the paste operation."""
        import struct

        # Pause the clipboard watcher so it doesn't record
        # the clipboard change we're about to make as a new copy
        if self.watcher:
            self.watcher.paused = True

        try:
            win32clipboard.OpenClipboard()
            win32clipboard.EmptyClipboard()

            if item["type"] in ("text", "url", "code", "bash"):
                # URLs, code snippets, and shell commands are all plain strings —
                # paste them exactly like regular text.
                win32clipboard.SetClipboardData(
                    win32con.CF_UNICODETEXT, item["content"])

            elif item["type"] == "file":
                # Windows CF_HDROP requires a precise binary structure:
                #
                # DROPFILES header (exactly 20 bytes):
                #   pFiles = 20  → offset where file list starts
                #   pt.x   = 0   → drop point x (unused)
                #   pt.y   = 0   → drop point y (unused)
                #   fNC    = 0   → not a non-client point
                #   fWide  = 1   → file paths are Unicode (UTF-16)
                #
                # Followed by each file path as UTF-16-LE + null terminator
                # Followed by a final double-null to end the list

                files = item["content"]
                if isinstance(files, list):
                    file_block = b""
                    for f in files:
                        file_block += f.encode("utf-16-le") + b"\x00\x00"
                    file_block += b"\x00\x00"  # End of list

                    # "<5I" = 5 unsigned ints, little-endian = exactly 20 bytes
                    header = struct.pack("<5I", 20, 0, 0, 0, 1)
                    dropfiles = header + file_block

                    win32clipboard.SetClipboardData(win32con.CF_HDROP, dropfiles)

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

        # Simulate Ctrl+V to trigger the paste in the active app
        pyautogui.hotkey("ctrl", "v")

        # Resume the clipboard watcher after a short delay
        # (enough time for the paste to complete)
        if self.watcher:
            time.sleep(0.5)
            self.watcher.paused = False


    def _toggle_pin(self, item):
        self.history.toggle_pin(item["id"])
        self._refresh()

    def _delete_item(self, item):
        # Remove from all profiles before deleting from history
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
        """Confirm focus truly left before hiding."""
        try:
            if self.window and not self.window.focus_get():
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
