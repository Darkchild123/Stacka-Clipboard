# ============================================================
# ClipDrop - dropdown_popup.py
# ============================================================
# This is the main visual interface of ClipDrop.
# It creates a popup window at the cursor position showing
# all clipboard history items with previews and action buttons.
# ============================================================

import tkinter as tk
from tkinter import ttk
from PIL import Image, ImageTk
import win32clipboard
import win32con
import pyautogui
import os
import time


# --- Colours used throughout the popup ---
COLOURS = {
    "bg":           "#1e1e2e",   # Dark background
    "bg_item":      "#2a2a3e",   # Slightly lighter for each item row
    "bg_hover":     "#3a3a5e",   # Even lighter when mouse hovers over an item
    "bg_pinned":    "#2d3748",   # Background for pinned items
    "accent":       "#4f46e5",   # Indigo — the brand colour
    "accent_light": "#6366f1",   # Lighter indigo for hover states
    "text":         "#e2e8f0",   # Light text
    "text_dim":     "#94a3b8",   # Dimmer text for source labels
    "text_preview": "#cbd5e1",   # Preview text colour
    "danger":       "#ef4444",   # Red for delete button
    "pin":          "#f59e0b",   # Amber for pin button
    "border":       "#3f3f5f",   # Subtle border colour
    "scrollbar":    "#3f3f5f",   # Scrollbar colour
}

# --- Fonts ---
FONT_PREVIEW = ("Segoe UI", 10)
FONT_SOURCE  = ("Segoe UI", 8)
FONT_ICON    = ("Segoe UI Emoji", 11)

# --- Sizes ---
POPUP_WIDTH    = 380   # Width of the popup in pixels
MAX_HEIGHT     = 480   # Maximum height before scrolling kicks in
ITEM_HEIGHT    = 64    # Height of each item row
THUMB_SIZE     = 40    # Thumbnail size for images
PADDING        = 10    # General padding


class DropdownPopup:

    def __init__(self, history_manager):
        self.history = history_manager
        self.root = None          # The main popup window
        self.canvas = None        # Scrollable area
        self.thumbnails = []      # Keep image references alive (Python GC issue)


    def show(self, x, y):
        """
        Shows the popup at position (x, y) — the mouse cursor coordinates.
        Builds the entire popup window fresh each time it's opened.
        """
        # Destroy any existing popup before opening a new one
        self.close()

        items = self.history.get_all()

        # If history is empty, don't show anything
        if not items:
            self._show_empty_popup(x, y)
            return

        # Create the main window
        self.root = tk.Tk()
        self.root.overrideredirect(True)   # No title bar — frameless window
        self.root.configure(bg=COLOURS["bg"])
        self.root.attributes("-topmost", True)  # Always on top of other windows

        # Add a subtle border around the popup
        border_frame = tk.Frame(self.root, bg=COLOURS["border"], padx=1, pady=1)
        border_frame.pack(fill="both", expand=True)

        inner_frame = tk.Frame(border_frame, bg=COLOURS["bg"])
        inner_frame.pack(fill="both", expand=True)

        # --- Header ---
        header = tk.Frame(inner_frame, bg=COLOURS["accent"], height=32)
        header.pack(fill="x")
        header.pack_propagate(False)

        tk.Label(
            header,
            text="📋  ClipDrop",
            bg=COLOURS["accent"],
            fg="white",
            font=("Segoe UI", 10, "bold"),
            padx=PADDING
        ).pack(side="left", fill="y")

        tk.Label(
            header,
            text=f"{len(items)} items",
            bg=COLOURS["accent"],
            fg="#c7d2fe",
            font=FONT_SOURCE,
            padx=PADDING
        ).pack(side="right", fill="y")

        # --- Scrollable Item List ---
        # Calculate how tall the list should be
        content_height = min(len(items) * ITEM_HEIGHT, MAX_HEIGHT)

        # Create a canvas (scrollable area) inside the popup
        self.canvas = tk.Canvas(
            inner_frame,
            bg=COLOURS["bg"],
            width=POPUP_WIDTH,
            height=content_height,
            highlightthickness=0
        )

        # Scrollbar on the right side
        scrollbar = tk.Scrollbar(
            inner_frame,
            orient="vertical",
            command=self.canvas.yview
        )
        self.canvas.configure(yscrollcommand=scrollbar.set)

        # Only show scrollbar if content is taller than the popup
        if len(items) * ITEM_HEIGHT > MAX_HEIGHT:
            scrollbar.pack(side="right", fill="y")

        self.canvas.pack(side="left", fill="both", expand=True)

        # A frame inside the canvas that holds all the item rows
        items_frame = tk.Frame(self.canvas, bg=COLOURS["bg"])
        self.canvas.create_window((0, 0), window=items_frame, anchor="nw")

        # Build each item row
        self.thumbnails = []  # Reset thumbnails list
        for index, item in enumerate(items):
            self._build_item_row(items_frame, item, index)

        # Update scroll region after all items are added
        items_frame.update_idletasks()
        self.canvas.configure(scrollregion=self.canvas.bbox("all"))

        # Enable mousewheel scrolling
        self.canvas.bind_all("<MouseWheel>", self._on_mousewheel)

        # Position the popup at the cursor, keeping it on screen
        self._position_popup(x, y)

        # Close popup if user clicks outside of it
        self.root.bind("<FocusOut>", lambda e: self.close())
        self.root.bind("<Escape>", lambda e: self.close())

        # Give the popup focus so FocusOut works correctly
        self.root.focus_force()
        self.root.mainloop()


    def close(self):
        """Closes and destroys the popup window."""
        if self.root:
            try:
                self.root.unbind_all("<MouseWheel>")
                self.root.destroy()
            except:
                pass
            self.root = None


    # ============================================================
    # BUILDING EACH ITEM ROW
    # ============================================================

    def _build_item_row(self, parent, item, index):
        """
        Builds one row in the popup for a single clipboard item.
        Each row contains: thumbnail/icon | preview + source | action buttons
        """
        is_pinned = item.get("pinned", False)

        # Choose background colour — pinned items look slightly different
        bg = COLOURS["bg_pinned"] if is_pinned else COLOURS["bg_item"]

        # Alternate very slightly for even/odd rows for readability
        if not is_pinned and index % 2 == 0:
            bg = COLOURS["bg"]

        # --- Outer row frame ---
        row = tk.Frame(
            parent,
            bg=bg,
            height=ITEM_HEIGHT,
            width=POPUP_WIDTH,
            pady=1
        )
        row.pack(fill="x")
        row.pack_propagate(False)

        # Hover effect — lighten background when mouse is over the row
        row.bind("<Enter>", lambda e, r=row: r.configure(bg=COLOURS["bg_hover"]))
        row.bind("<Leave>", lambda e, r=row, b=bg: r.configure(bg=b))

        # --- Thumbnail / Icon (left side) ---
        thumb_frame = tk.Frame(row, bg=bg, width=THUMB_SIZE + 10)
        thumb_frame.pack(side="left", fill="y", padx=(8, 4))
        thumb_frame.pack_propagate(False)

        self._build_thumbnail(thumb_frame, item, bg)

        # --- Preview Text and Source (middle) ---
        text_frame = tk.Frame(row, bg=bg)
        text_frame.pack(side="left", fill="both", expand=True, pady=8)

        preview = self.history.get_preview(item)
        pin_badge = " 📌" if is_pinned else ""

        # Preview label (main text shown for the item)
        preview_label = tk.Label(
            text_frame,
            text=preview + pin_badge,
            bg=bg,
            fg=COLOURS["text_preview"],
            font=FONT_PREVIEW,
            anchor="w",
            wraplength=190,
            justify="left"
        )
        preview_label.pack(anchor="w")

        # Source label (where it was copied from)
        source_text = f"From: {item.get('source', 'Unknown')}"
        source_label = tk.Label(
            text_frame,
            text=source_text,
            bg=bg,
            fg=COLOURS["text_dim"],
            font=FONT_SOURCE,
            anchor="w"
        )
        source_label.pack(anchor="w")

        # Make the text area clickable — clicking it pastes the item
        for widget in [row, text_frame, preview_label, source_label]:
            widget.bind("<Button-1>", lambda e, i=item: self._paste_item(i))

        # --- Action Buttons (right side) ---
        btn_frame = tk.Frame(row, bg=bg)
        btn_frame.pack(side="right", fill="y", padx=(0, 6))

        # Pin button
        pin_symbol = "📌" if is_pinned else "📍"
        self._make_button(
            btn_frame, pin_symbol,
            lambda i=item: self._toggle_pin(i),
            COLOURS["pin"]
        )

        # Move Up button
        self._make_button(
            btn_frame, "↑",
            lambda i=item: self._move_up(i),
            COLOURS["text_dim"]
        )

        # Move Down button
        self._make_button(
            btn_frame, "↓",
            lambda i=item: self._move_down(i),
            COLOURS["text_dim"]
        )

        # Delete button
        self._make_button(
            btn_frame, "✕",
            lambda i=item: self._delete_item(i),
            COLOURS["danger"]
        )


    def _build_thumbnail(self, parent, item, bg):
        """
        Builds the left-side thumbnail or icon for an item.
        - Images: shows a small thumbnail
        - Files: shows a file emoji icon
        - Text: shows a text emoji icon
        """
        if item["type"] == "image":
            try:
                img = Image.open(item["content"])
                img.thumbnail((THUMB_SIZE, THUMB_SIZE))
                photo = ImageTk.PhotoImage(img)
                self.thumbnails.append(photo)  # Keep reference alive!
                tk.Label(parent, image=photo, bg=bg).pack(expand=True)
                return
            except:
                pass  # Fall through to emoji if image fails

        # Emoji icon for text or file types
        icon = "📄" if item["type"] == "text" else "📁"
        tk.Label(
            parent,
            text=icon,
            bg=bg,
            font=("Segoe UI Emoji", 20)
        ).pack(expand=True)


    def _make_button(self, parent, text, command, colour):
        """
        Creates a small action button (pin, up, down, delete).
        Designed to be compact and unobtrusive.
        """
        btn = tk.Label(
            parent,
            text=text,
            bg=COLOURS["bg_item"],
            fg=colour,
            font=("Segoe UI", 9),
            padx=4,
            pady=2,
            cursor="hand2"  # Shows a hand cursor on hover
        )
        btn.pack(side="top", pady=1)
        btn.bind("<Button-1>", lambda e: command())
        btn.bind("<Enter>", lambda e: btn.configure(bg=COLOURS["bg_hover"]))
        btn.bind("<Leave>", lambda e: btn.configure(bg=COLOURS["bg_item"]))


    # ============================================================
    # ACTIONS
    # ============================================================

    def _paste_item(self, item):
        """
        Pastes the selected item:
        1. Puts the item's content back into the Windows clipboard
        2. Closes the popup
        3. Simulates Ctrl+V to paste it into whatever app is active
        """
        self.close()

        # Small delay to let the popup close before simulating keypress
        time.sleep(0.1)

        try:
            win32clipboard.OpenClipboard()
            win32clipboard.EmptyClipboard()

            if item["type"] == "text":
                win32clipboard.SetClipboardData(
                    win32con.CF_UNICODETEXT,
                    item["content"]
                )

            elif item["type"] == "file":
                # For files, we restore the file drop list
                files = item["content"]
                if isinstance(files, list):
                    win32clipboard.SetClipboardData(
                        win32con.CF_HDROP,
                        files
                    )

            elif item["type"] == "image":
                # For images, open the saved PNG and put it on the clipboard
                img = Image.open(item["content"])
                import io
                output = io.BytesIO()
                img.convert("RGB").save(output, "BMP")
                data = output.getvalue()[14:]  # BMP header offset
                output.close()
                win32clipboard.SetClipboardData(win32con.CF_DIB, data)

            win32clipboard.CloseClipboard()

        except Exception as e:
            print(f"Paste error: {e}")
            try:
                win32clipboard.CloseClipboard()
            except:
                pass
            return

        # Simulate Ctrl+V to trigger the actual paste
        pyautogui.hotkey("ctrl", "v")


    def _toggle_pin(self, item):
        """Pins or unpins an item, then refreshes the popup."""
        self.history.toggle_pin(item["id"])
        self._refresh()


    def _delete_item(self, item):
        """Deletes an item from history, then refreshes the popup."""
        self.history.delete_item(item["id"])
        self._refresh()


    def _move_up(self, item):
        """Moves an item up in the list, then refreshes the popup."""
        self.history.move_up(item["id"])
        self._refresh()


    def _move_down(self, item):
        """Moves an item down in the list, then refreshes the popup."""
        self.history.move_down(item["id"])
        self._refresh()


    def _refresh(self):
        """
        Refreshes the popup to reflect any changes made
        (after pinning, deleting, or reordering).
        Gets the current mouse position and reopens the popup there.
        """
        x, y = pyautogui.position()
        self.close()
        self.show(x, y)


    # ============================================================
    # HELPERS
    # ============================================================

    def _position_popup(self, x, y):
        """
        Places the popup window at (x, y) while making sure
        it doesn't go off the edges of the screen.
        """
        self.root.update_idletasks()
        popup_w = self.root.winfo_width()
        popup_h = self.root.winfo_height()
        screen_w = self.root.winfo_screenwidth()
        screen_h = self.root.winfo_screenheight()

        # Adjust if popup would go off the right edge
        if x + popup_w > screen_w:
            x = screen_w - popup_w - 10

        # Adjust if popup would go off the bottom edge
        if y + popup_h > screen_h:
            y = screen_h - popup_h - 10

        self.root.geometry(f"+{x}+{y}")


    def _on_mousewheel(self, event):
        """Handles scrolling the list with the mouse wheel."""
        self.canvas.yview_scroll(int(-1 * (event.delta / 120)), "units")


    def _show_empty_popup(self, x, y):
        """
        Shows a small message when the clipboard history is empty.
        """
        root = tk.Tk()
        root.overrideredirect(True)
        root.configure(bg=COLOURS["bg"])
        root.attributes("-topmost", True)

        tk.Label(
            root,
            text="📋  No clipboard history yet.\n Copy something to get started!",
            bg=COLOURS["bg"],
            fg=COLOURS["text_dim"],
            font=FONT_PREVIEW,
            padx=20,
            pady=16
        ).pack()

        root.geometry(f"+{x}+{y}")
        root.focus_force()
        root.bind("<FocusOut>", lambda e: root.destroy())
        root.bind("<Escape>", lambda e: root.destroy())
        root.mainloop()
