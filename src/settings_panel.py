# ============================================================
# ClipDrop - settings_panel.py
# ============================================================
# This file creates the Settings window for ClipDrop.
# It lets the user control how ClipDrop behaves —
# history size, clearing history, and viewing app info.
# Opened from the system tray icon menu.
# ============================================================

import tkinter as tk
from tkinter import messagebox
import webbrowser


# --- App Information ---
APP_NAME    = "ClipDrop"
APP_VERSION = "1.0.0"
APP_AUTHOR  = "Cosmas"
GITHUB_URL  = "https://github.com/Darkchild123/Project-ClipDrop"

# --- Colours (matching the dropdown popup theme) ---
COLOURS = {
    "bg":           "#1e1e2e",
    "bg_section":   "#2a2a3e",
    "bg_input":     "#13131f",
    "accent":       "#4f46e5",
    "accent_hover": "#6366f1",
    "text":         "#e2e8f0",
    "text_dim":     "#94a3b8",
    "danger":       "#ef4444",
    "danger_hover": "#dc2626",
    "success":      "#22c55e",
    "border":       "#3f3f5f",
}

# --- Fonts ---
FONT_TITLE   = ("Segoe UI", 13, "bold")
FONT_HEADING = ("Segoe UI", 10, "bold")
FONT_BODY    = ("Segoe UI", 10)
FONT_SMALL   = ("Segoe UI", 8)
FONT_LINK    = ("Segoe UI", 9, "underline")


class SettingsPanel:

    def __init__(self, history_manager):
        self.history = history_manager
        self.root = None


    def show(self):
        """
        Builds and displays the settings window.
        The window is centred on the screen when it opens.
        """
        self.root = tk.Tk()
        self.root.title("ClipDrop Settings")
        self.root.configure(bg=COLOURS["bg"])
        self.root.resizable(False, False)       # Fixed size — no resizing
        self.root.attributes("-topmost", True)  # Always on top

        # Set the window size and centre it on screen
        window_width  = 420
        window_height = 520
        self._centre_window(window_width, window_height)

        # Build all sections of the settings panel
        self._build_header()
        self._build_divider()
        self._build_history_section()
        self._build_divider()
        self._build_danger_section()
        self._build_divider()
        self._build_info_section()
        self._build_footer()

        # Handle the window close button (X)
        self.root.protocol("WM_DELETE_WINDOW", self._close)

        self.root.mainloop()


    # ============================================================
    # BUILDING SECTIONS
    # ============================================================

    def _build_header(self):
        """
        The top header bar with the ClipDrop logo and title.
        """
        header = tk.Frame(self.root, bg=COLOURS["accent"], height=60)
        header.pack(fill="x")
        header.pack_propagate(False)

        tk.Label(
            header,
            text="📋  ClipDrop Settings",
            bg=COLOURS["accent"],
            fg="white",
            font=FONT_TITLE,
            pady=16
        ).pack()


    def _build_history_section(self):
        """
        Section for controlling clipboard history behaviour.
        Lets the user set how many items ClipDrop remembers.
        """
        section = tk.Frame(self.root, bg=COLOURS["bg"], padx=24, pady=16)
        section.pack(fill="x")

        # Section heading
        tk.Label(
            section,
            text="🗂   History",
            bg=COLOURS["bg"],
            fg=COLOURS["text"],
            font=FONT_HEADING,
            anchor="w"
        ).pack(fill="x")

        tk.Label(
            section,
            text="Control how many items ClipDrop keeps in memory.",
            bg=COLOURS["bg"],
            fg=COLOURS["text_dim"],
            font=FONT_SMALL,
            anchor="w"
        ).pack(fill="x", pady=(2, 12))

        # --- History Size Limit ---
        row = tk.Frame(section, bg=COLOURS["bg"])
        row.pack(fill="x")

        tk.Label(
            row,
            text="History size limit:",
            bg=COLOURS["bg"],
            fg=COLOURS["text"],
            font=FONT_BODY,
            width=20,
            anchor="w"
        ).pack(side="left")

        # A number entry field for the history limit
        # StringVar is a special tkinter variable that we can track for changes
        self.limit_var = tk.StringVar(value=str(self.history.get_limit()))

        limit_entry = tk.Entry(
            row,
            textvariable=self.limit_var,
            bg=COLOURS["bg_input"],
            fg=COLOURS["text"],
            insertbackground=COLOURS["text"],  # Cursor colour
            font=FONT_BODY,
            width=6,
            relief="flat",
            justify="center",
            bd=6
        )
        limit_entry.pack(side="left", padx=(0, 8))

        tk.Label(
            row,
            text="items",
            bg=COLOURS["bg"],
            fg=COLOURS["text_dim"],
            font=FONT_BODY
        ).pack(side="left")

        # Save button for the history limit
        self._make_button(
            section,
            text="Save Limit",
            command=self._save_limit,
            colour=COLOURS["accent"],
            hover=COLOURS["accent_hover"],
            pady=(10, 0)
        )

        # Feedback label — shows "Saved!" after clicking Save
        self.save_feedback = tk.Label(
            section,
            text="",
            bg=COLOURS["bg"],
            fg=COLOURS["success"],
            font=FONT_SMALL
        )
        self.save_feedback.pack(anchor="w", pady=(4, 0))


    def _build_danger_section(self):
        """
        The danger zone — contains the Clear All History button.
        Styled in red to signal it's a destructive action.
        """
        section = tk.Frame(self.root, bg=COLOURS["bg"], padx=24, pady=16)
        section.pack(fill="x")

        tk.Label(
            section,
            text="⚠️   Danger Zone",
            bg=COLOURS["bg"],
            fg=COLOURS["danger"],
            font=FONT_HEADING,
            anchor="w"
        ).pack(fill="x")

        tk.Label(
            section,
            text="These actions cannot be undone.",
            bg=COLOURS["bg"],
            fg=COLOURS["text_dim"],
            font=FONT_SMALL,
            anchor="w"
        ).pack(fill="x", pady=(2, 12))

        self._make_button(
            section,
            text="🧹  Clear All History",
            command=self._confirm_clear,
            colour=COLOURS["danger"],
            hover=COLOURS["danger_hover"]
        )


    def _build_info_section(self):
        """
        App information section — version, author, and GitHub link.
        """
        section = tk.Frame(self.root, bg=COLOURS["bg"], padx=24, pady=16)
        section.pack(fill="x")

        tk.Label(
            section,
            text="ℹ️   About ClipDrop",
            bg=COLOURS["bg"],
            fg=COLOURS["text"],
            font=FONT_HEADING,
            anchor="w"
        ).pack(fill="x", pady=(0, 10))

        # Info rows
        info_rows = [
            ("Version",  APP_VERSION),
            ("Author",   APP_AUTHOR),
            ("Platform", "Windows"),
        ]

        for label, value in info_rows:
            row = tk.Frame(section, bg=COLOURS["bg"])
            row.pack(fill="x", pady=2)

            tk.Label(
                row,
                text=label + ":",
                bg=COLOURS["bg"],
                fg=COLOURS["text_dim"],
                font=FONT_BODY,
                width=12,
                anchor="w"
            ).pack(side="left")

            tk.Label(
                row,
                text=value,
                bg=COLOURS["bg"],
                fg=COLOURS["text"],
                font=FONT_BODY,
                anchor="w"
            ).pack(side="left")

        # GitHub link — clicking it opens the browser
        row = tk.Frame(section, bg=COLOURS["bg"])
        row.pack(fill="x", pady=(8, 0))

        tk.Label(
            row,
            text="GitHub:",
            bg=COLOURS["bg"],
            fg=COLOURS["text_dim"],
            font=FONT_BODY,
            width=12,
            anchor="w"
        ).pack(side="left")

        link = tk.Label(
            row,
            text=GITHUB_URL,
            bg=COLOURS["bg"],
            fg=COLOURS["accent_hover"],
            font=FONT_LINK,
            cursor="hand2",
            anchor="w"
        )
        link.pack(side="left")
        link.bind("<Button-1>", lambda e: webbrowser.open(GITHUB_URL))
        link.bind("<Enter>", lambda e: link.configure(fg="white"))
        link.bind("<Leave>", lambda e: link.configure(fg=COLOURS["accent_hover"]))


    def _build_footer(self):
        """
        A simple footer at the bottom with a Close button.
        """
        footer = tk.Frame(self.root, bg=COLOURS["bg_section"], pady=16)
        footer.pack(fill="x", side="bottom")

        self._make_button(
            footer,
            text="Close",
            command=self._close,
            colour=COLOURS["accent"],
            hover=COLOURS["accent_hover"],
            width=12
        )


    def _build_divider(self):
        """
        A thin horizontal line used to separate sections visually.
        """
        tk.Frame(
            self.root,
            bg=COLOURS["border"],
            height=1
        ).pack(fill="x", padx=24)


    # ============================================================
    # ACTIONS
    # ============================================================

    def _save_limit(self):
        """
        Reads the value from the history limit field,
        validates it, and saves it to the history manager.
        """
        try:
            value = int(self.limit_var.get())

            if value < 1:
                messagebox.showwarning(
                    "Invalid Value",
                    "History limit must be at least 1.",
                    parent=self.root
                )
                return

            if value > 1000:
                messagebox.showwarning(
                    "Invalid Value",
                    "History limit cannot exceed 1000 items.",
                    parent=self.root
                )
                return

            # Save the new limit
            self.history.set_limit(value)

            # Show "Saved!" feedback briefly then clear it
            self.save_feedback.configure(text="✓  Saved!")
            self.root.after(2000, lambda: self.save_feedback.configure(text=""))

        except ValueError:
            messagebox.showerror(
                "Invalid Value",
                "Please enter a whole number for the history limit.",
                parent=self.root
            )


    def _confirm_clear(self):
        """
        Shows a confirmation dialog before clearing all history.
        This prevents accidental data loss — the user must confirm.
        """
        confirmed = messagebox.askyesno(
            title="Clear History",
            message="Are you sure you want to clear all clipboard history?\n\nThis cannot be undone.",
            icon="warning",
            parent=self.root
        )

        if confirmed:
            self.history.clear_all()
            messagebox.showinfo(
                title="Done",
                message="Clipboard history has been cleared.",
                parent=self.root
            )


    def _close(self):
        """Closes the settings window."""
        self.root.destroy()


    # ============================================================
    # HELPERS
    # ============================================================

    def _make_button(self, parent, text, command, colour, hover, pady=(0,0), width=None):
        """
        Creates a styled button with hover effects.
        Used throughout the settings panel for consistency.
        """
        kwargs = dict(
            text=text,
            bg=colour,
            fg="white",
            font=FONT_BODY,
            relief="flat",
            cursor="hand2",
            padx=16,
            pady=8,
            bd=0
        )
        if width:
            kwargs["width"] = width

        btn = tk.Label(parent, **kwargs)
        btn.pack(pady=pady)
        btn.bind("<Button-1>", lambda e: command())
        btn.bind("<Enter>", lambda e: btn.configure(bg=hover))
        btn.bind("<Leave>", lambda e: btn.configure(bg=colour))


    def _centre_window(self, width, height):
        """
        Calculates the correct position to centre the window
        on the user's screen, regardless of screen size.
        """
        screen_w = self.root.winfo_screenwidth()
        screen_h = self.root.winfo_screenheight()
        x = (screen_w // 2) - (width // 2)
        y = (screen_h // 2) - (height // 2)
        self.root.geometry(f"{width}x{height}+{x}+{y}")
