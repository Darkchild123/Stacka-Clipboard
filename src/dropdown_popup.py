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
from PIL import Image, ImageTk
import win32clipboard
import win32con
import win32gui
import pyautogui
import os
import time
import io

DRAG_THRESHOLD = 6   # pixels of movement before drag mode activates


# --- Colours ---
COLOURS = {
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
        # Destroy any existing popup first
        self._do_hide()

        self.thumbnails = []
        # Use active profile's filtered items if profiles are available,
        # otherwise fall back to full history
        if self.profiles:
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


    def _fade_in(self, alpha=0.0):
        """
        Smoothly fades the popup in from transparent to fully visible.
        Steps up opacity by 0.08 every 15ms — reaches full opacity in ~190ms.
        """
        if not self.window:
            return
        alpha = min(alpha + 0.08, 1.0)
        try:
            self.window.attributes("-alpha", alpha)
        except Exception:
            return
        if alpha < 1.0:
            self.root.after(15, lambda: self._fade_in(alpha))


    # ============================================================
    # BUILDING CONTENT
    # ============================================================

    def _build_content(self, items):
        """Builds the header and scrollable item list."""

        # Border frame
        border = tk.Frame(self.window, bg=COLOURS["border"], padx=1, pady=1)
        border.pack(fill="both", expand=True)

        inner = tk.Frame(border, bg=COLOURS["bg"])
        inner.pack(fill="both", expand=True)

        # Header — drag handle + profile switcher
        header = tk.Frame(inner, bg=COLOURS["accent"], height=32)
        header.pack(fill="x")
        header.pack_propagate(False)

        lbl_title = tk.Label(
            header, text="📋  ClipDrop  ✥",
            bg=COLOURS["accent"], fg="white",
            font=("Segoe UI", 10, "bold"), padx=PADDING
        )
        lbl_title.pack(side="left", fill="y")

        lbl_count = tk.Label(
            header, text=f"{len(items)} items",
            bg=COLOURS["accent"], fg="#c7d2fe",
            font=FONT_SOURCE, padx=PADDING
        )
        lbl_count.pack(side="right", fill="y")

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
        for widget in (header, lbl_title, lbl_count):
            self._make_draggable(widget)

        # Scrollable canvas
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

        for index, item in enumerate(items):
            self._build_item_row(items_frame, item, index)

        items_frame.update_idletasks()
        canvas.configure(scrollregion=canvas.bbox("all"))

        canvas.bind_all("<MouseWheel>",
            lambda e: canvas.yview_scroll(int(-1*(e.delta/120)), "units"))


    def _build_empty_state(self):
        """Shows a message when history is empty."""
        tk.Label(
            self.window,
            text="📋  No clipboard history yet.\nCopy something to get started!",
            bg=COLOURS["bg"], fg=COLOURS["text_dim"],
            font=FONT_PREVIEW, padx=20, pady=16
        ).pack()


    def _build_item_row(self, parent, item, index):
        """Builds one row for a single clipboard item."""
        is_pinned = item.get("pinned", False)
        bg = COLOURS["bg_pinned"] if is_pinned else (
            COLOURS["bg"] if index % 2 == 0 else COLOURS["bg_item"]
        )

        row = tk.Frame(parent, bg=bg, height=ITEM_HEIGHT, width=POPUP_WIDTH)
        row.pack(fill="x")
        row.pack_propagate(False)

        # Thin separator line between items
        sep = tk.Frame(parent, bg=COLOURS["border"], height=1)
        sep.pack(fill="x")

        def _enter(e, r=row, s=sep):
            r.configure(bg=COLOURS["bg_hover"])
            s.configure(bg=COLOURS["bg_hover"])
        def _leave(e, r=row, s=sep, b=bg):
            r.configure(bg=b)
            s.configure(bg=COLOURS["border"])

        row.bind("<Enter>", _enter)
        row.bind("<Leave>", _leave)

        # Thumbnail — smaller column so text gets more room
        thumb_frame = tk.Frame(row, bg=bg, width=THUMB_SIZE + 6)
        thumb_frame.pack(side="left", fill="y", padx=(6, 2))
        thumb_frame.pack_propagate(False)
        self._build_thumbnail(thumb_frame, item, bg)

        # Preview and source text — tight vertical padding so text fills the row
        text_frame = tk.Frame(row, bg=bg)
        text_frame.pack(side="left", fill="both", expand=True, pady=(4, 4))

        preview   = self.history.get_preview(item)
        pin_badge = " 📌" if is_pinned else ""

        preview_label = tk.Label(
            text_frame, text=preview + pin_badge,
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

        # Action buttons — 2×2 grid so each button has comfortable click space
        #   col 0  col 1
        #   📌     ↑
        #   ✕      ↓
        btn_frame = tk.Frame(row, bg=bg)
        btn_frame.pack(side="right", fill="y", padx=(0, 6))
        # Centre the grid vertically inside the row
        btn_frame.pack_configure(anchor="center")

        pin_symbol = "📌" if is_pinned else "📍"
        grid_btns = [
            (pin_symbol, lambda i=item: self._toggle_pin(i),  COLOURS["pin"],      0, 0),
            ("↑",        lambda i=item: self._move_up(i),     COLOURS["text_dim"], 0, 1),
            ("✕",        lambda i=item: self._delete_item(i), COLOURS["danger"],   1, 0),
            ("↓",        lambda i=item: self._move_down(i),   COLOURS["text_dim"], 1, 1),
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
        if self.window:
            x = self.window.winfo_x()
            y = self.window.winfo_y()
            self._build_and_show(x, y)


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
        """Shows image thumbnail or emoji icon."""
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

        icon = "📄" if item["type"] == "text" else "📁"
        tk.Label(parent, text=icon, bg=bg,
                 font=("Segoe UI Emoji", 16)).pack(expand=True)


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

            if item["type"] == "text":
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
