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
import pyautogui
import os
import time
import io


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

POPUP_WIDTH  = 380
MAX_HEIGHT   = 480
ITEM_HEIGHT  = 64
THUMB_SIZE   = 40
PADDING      = 10


class DropdownPopup:

    def __init__(self, root, history_manager, watcher=None):
        """
        root            — the shared tkinter root from main.py
        history_manager — the app's history manager
        watcher         — the clipboard watcher (so we can pause it during paste)
        """
        self.root    = root
        self.history = history_manager
        self.watcher = watcher    # Used to pause watching during paste
        self.window  = None       # The popup Toplevel window
        self.thumbnails = []      # Keep image references alive

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

        # Now show it
        self.window.deiconify()
        self.window.lift()
        self.window.focus_force()


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

        # Header
        header = tk.Frame(inner, bg=COLOURS["accent"], height=32)
        header.pack(fill="x")
        header.pack_propagate(False)

        tk.Label(
            header, text="📋  ClipDrop",
            bg=COLOURS["accent"], fg="white",
            font=("Segoe UI", 10, "bold"), padx=PADDING
        ).pack(side="left", fill="y")

        tk.Label(
            header, text=f"{len(items)} items",
            bg=COLOURS["accent"], fg="#c7d2fe",
            font=FONT_SOURCE, padx=PADDING
        ).pack(side="right", fill="y")

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

        row.bind("<Enter>", lambda e, r=row: r.configure(bg=COLOURS["bg_hover"]))
        row.bind("<Leave>", lambda e, r=row, b=bg: r.configure(bg=b))

        # Thumbnail
        thumb_frame = tk.Frame(row, bg=bg, width=THUMB_SIZE + 10)
        thumb_frame.pack(side="left", fill="y", padx=(8, 4))
        thumb_frame.pack_propagate(False)
        self._build_thumbnail(thumb_frame, item, bg)

        # Preview and source text
        text_frame = tk.Frame(row, bg=bg)
        text_frame.pack(side="left", fill="both", expand=True, pady=8)

        preview   = self.history.get_preview(item)
        pin_badge = " 📌" if is_pinned else ""

        preview_label = tk.Label(
            text_frame, text=preview + pin_badge,
            bg=bg, fg=COLOURS["text_preview"],
            font=FONT_PREVIEW, anchor="w",
            wraplength=190, justify="left"
        )
        preview_label.pack(anchor="w")

        source_label = tk.Label(
            text_frame, text=f"From: {item.get('source', 'Unknown')}",
            bg=bg, fg=COLOURS["text_dim"],
            font=FONT_SOURCE, anchor="w"
        )
        source_label.pack(anchor="w")

        # Click to paste
        for widget in [row, text_frame, preview_label, source_label]:
            widget.bind("<Button-1>", lambda e, i=item: self._paste_item(i))

        # Action buttons
        btn_frame = tk.Frame(row, bg=bg)
        btn_frame.pack(side="right", fill="y", padx=(0, 6))

        pin_symbol = "📌" if is_pinned else "📍"
        self._make_button(btn_frame, pin_symbol,
            lambda i=item: self._toggle_pin(i), COLOURS["pin"])
        self._make_button(btn_frame, "↑",
            lambda i=item: self._move_up(i), COLOURS["text_dim"])
        self._make_button(btn_frame, "↓",
            lambda i=item: self._move_down(i), COLOURS["text_dim"])
        self._make_button(btn_frame, "✕",
            lambda i=item: self._delete_item(i), COLOURS["danger"])


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
                 font=("Segoe UI Emoji", 20)).pack(expand=True)


    def _make_button(self, parent, text, command, colour):
        """Creates a small styled action button."""
        btn = tk.Label(
            parent, text=text,
            bg=COLOURS["bg_item"], fg=colour,
            font=("Segoe UI", 9),
            padx=4, pady=2, cursor="hand2"
        )
        btn.pack(side="top", pady=1)
        btn.bind("<Button-1>", lambda e: command())
        btn.bind("<Enter>", lambda e: btn.configure(bg=COLOURS["bg_hover"]))
        btn.bind("<Leave>", lambda e: btn.configure(bg=COLOURS["bg_item"]))


    # ============================================================
    # ACTIONS
    # ============================================================

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
