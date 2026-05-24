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

    def __init__(self, history_manager, profile_manager=None):
        self.history  = history_manager
        self.profiles = profile_manager
        self.root     = None


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
        window_height = 680
        self._centre_window(window_width, window_height)

        # Build all sections of the settings panel
        self._build_header()
        self._build_divider()
        self._build_history_section()
        self._build_divider()
        self._build_profiles_section()
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


    def _build_profiles_section(self):
        """
        Profile management section.
        Lets the user create, rename, delete, and reorder profiles.
        """
        if not self.profiles:
            return

        section = tk.Frame(self.root, bg=COLOURS["bg"], padx=24, pady=16)
        section.pack(fill="x")

        tk.Label(section, text="👤  Profiles",
                 bg=COLOURS["bg"], fg=COLOURS["text"],
                 font=FONT_HEADING, anchor="w").pack(fill="x")

        tk.Label(section,
                 text="Organise your clipboard into named workflow collections.",
                 bg=COLOURS["bg"], fg=COLOURS["text_dim"],
                 font=FONT_SMALL, anchor="w").pack(fill="x", pady=(2, 10))

        # Profile list — a scrollable listbox
        list_frame = tk.Frame(section, bg=COLOURS["border"], padx=1, pady=1)
        list_frame.pack(fill="x")

        self.profile_listbox = tk.Listbox(
            list_frame,
            bg=COLOURS["bg_input"], fg=COLOURS["text"],
            selectbackground=COLOURS["accent"],
            selectforeground="white",
            font=FONT_BODY,
            height=5,
            relief="flat",
            bd=0,
            activestyle="none"
        )
        self.profile_listbox.pack(fill="x")
        self._refresh_profile_list()

        # Action buttons row
        def _make_profile_btn(parent, label, cmd, bg_col, hover_col):
            btn = tk.Label(
                parent, text=label,
                bg=bg_col, fg="white",
                font=("Segoe UI", 9), padx=10, pady=5,
                cursor="hand2", relief="flat"
            )
            btn.pack(side="left", padx=(0, 6))
            btn.bind("<Button-1>", lambda e, c=cmd: c())
            btn.bind("<Enter>",  lambda e, b=btn, h=hover_col: b.configure(bg=h))
            btn.bind("<Leave>",  lambda e, b=btn, bg=bg_col:   b.configure(bg=bg))

        # Row 1 — create / rename / delete
        row1 = tk.Frame(section, bg=COLOURS["bg"])
        row1.pack(fill="x", pady=(8, 4))
        _make_profile_btn(row1, "＋ New",    self._new_profile,            COLOURS["bg_section"], COLOURS["accent"])
        _make_profile_btn(row1, "✎ Rename",  self._rename_profile,         COLOURS["bg_section"], COLOURS["accent"])
        _make_profile_btn(row1, "✕ Delete",  self._delete_profile,         COLOURS["bg_section"], COLOURS["accent"])

        # Row 2 — reorder / clear
        row2 = tk.Frame(section, bg=COLOURS["bg"])
        row2.pack(fill="x", pady=(0, 0))
        _make_profile_btn(row2, "↑  Move Up",   self._move_profile_up,        COLOURS["bg_section"], COLOURS["accent"])
        _make_profile_btn(row2, "↓  Move Down", self._move_profile_down,      COLOURS["bg_section"], COLOURS["accent"])
        _make_profile_btn(row2, "🧹 Clear",     self._clear_selected_profile, COLOURS["danger"],     COLOURS["danger_hover"])


    def _refresh_profile_list(self):
        """Rebuilds the profile listbox from current profile data."""
        if not hasattr(self, "profile_listbox"):
            return
        self.profile_listbox.delete(0, "end")
        for profile in self.profiles.get_all_profiles():
            count  = self.profiles.get_profile_item_count(profile["id"])
            active = "● " if profile["id"] == self.profiles.active_id else "  "
            lock   = " 🔒" if profile.get("built_in") else ""
            self.profile_listbox.insert(
                "end",
                f"{active}{profile['name']}{lock}  ({count} items)"
            )


    def _selected_profile(self):
        """Returns the profile dict for the currently selected listbox row."""
        sel = self.profile_listbox.curselection()
        if not sel:
            return None
        idx = sel[0]
        return self.profiles.get_all_profiles()[idx]


    def _new_profile(self):
        """Opens a dialog to create a new profile."""
        from tkinter import simpledialog
        name = simpledialog.askstring(
            "New Profile", "Enter a name for the new profile:",
            parent=self.root
        )
        if name and name.strip():
            self.profiles.create_profile(name.strip())
            self._refresh_profile_list()


    def _rename_profile(self):
        """Renames the selected profile."""
        profile = self._selected_profile()
        if not profile:
            messagebox.showinfo("Rename Profile",
                                "Select a profile first.", parent=self.root)
            return
        if profile.get("built_in"):
            messagebox.showinfo("Rename Profile",
                                "The General profile cannot be renamed.",
                                parent=self.root)
            return
        from tkinter import simpledialog
        new_name = simpledialog.askstring(
            "Rename Profile",
            f"New name for '{profile['name']}':",
            initialvalue=profile["name"],
            parent=self.root
        )
        if new_name and new_name.strip():
            self.profiles.rename_profile(profile["id"], new_name.strip())
            self._refresh_profile_list()


    def _delete_profile(self):
        """Deletes the selected profile after confirmation."""
        profile = self._selected_profile()
        if not profile:
            messagebox.showinfo("Delete Profile",
                                "Select a profile first.", parent=self.root)
            return
        if profile.get("built_in"):
            messagebox.showinfo("Delete Profile",
                                "The General profile cannot be deleted.",
                                parent=self.root)
            return
        confirmed = messagebox.askyesno(
            "Delete Profile",
            f"Delete profile '{profile['name']}'?\n\n"
            "Items in this profile will not be deleted — they remain in General.",
            parent=self.root
        )
        if confirmed:
            self.profiles.delete_profile(profile["id"])
            self._refresh_profile_list()


    def _clear_selected_profile(self):
        """
        Clears the profile selected in the listbox.

        General selected  → asks for confirmation, then deletes all history items.
        Named profile     → asks for confirmation, then removes all items from
                            that profile only. Items stay in General and other profiles.
        """
        profile = self._selected_profile()
        if not profile:
            messagebox.showinfo("Clear Profile",
                                "Select a profile from the list first.",
                                parent=self.root)
            return

        if profile["id"] == "general":
            confirmed = messagebox.askyesno(
                title="Clear All History",
                message="Clear the entire clipboard history?\n\nThis will delete all items from General and cannot be undone.",
                icon="warning",
                parent=self.root
            )
            if confirmed:
                self.history.clear_all()
                self._refresh_profile_list()
                messagebox.showinfo("Done", "All clipboard history has been cleared.",
                                    parent=self.root)
        else:
            profile_name = profile["name"]
            confirmed = messagebox.askyesno(
                title="Clear Profile",
                message=(
                    f"Clear all items from \"{profile_name}\"?\n\n"
                    "Items will not be deleted — they will still appear in General "
                    "and any other profiles they belong to.\n\n"
                    "This cannot be undone."
                ),
                icon="warning",
                parent=self.root
            )
            if confirmed:
                self.profiles.clear_profile(profile["id"])
                self._refresh_profile_list()
                messagebox.showinfo("Done",
                                    f"\"{profile_name}\" profile has been cleared.",
                                    parent=self.root)


    def _move_profile_up(self):
        profile = self._selected_profile()
        if profile:
            self.profiles.move_up(profile["id"])
            self._refresh_profile_list()


    def _move_profile_down(self):
        profile = self._selected_profile()
        if profile:
            self.profiles.move_down(profile["id"])
            self._refresh_profile_list()


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
