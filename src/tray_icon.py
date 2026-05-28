# ============================================================
# ClipDrop - tray_icon.py
# ============================================================
# This file creates and manages the ClipDrop system tray icon.
# It sits in the bottom-right corner of Windows (the taskbar tray)
# and gives the user quick access to settings and controls.
# ============================================================

import pystray
from pystray import MenuItem as item
from PIL import Image, ImageDraw
import threading
import os
import sys


# Path to the icon file in the assets folder
BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
ICON_PATH = os.path.join(BASE_DIR, "assets", "icon.png")


class TrayIcon:

    def __init__(self, history_manager, profile_manager, root):
        # Store the history manager so we can call clear_all() from the tray
        self.history  = history_manager
        self.profiles = profile_manager

        # The shared tkinter root — used to safely schedule UI actions
        self.root = root

        # settings_panel will be imported here when needed
        # (we import it late to avoid circular imports)
        self.settings_window = None

        # Load or generate the tray icon image
        self.icon_image = self._load_icon()

        # Build the right-click menu for the tray icon.
        # The Switch Profile submenu is generated dynamically so it always
        # reflects the current list of profiles.
        self.menu = pystray.Menu(
            item("ClipDrop", self._do_nothing, enabled=False),
            pystray.Menu.SEPARATOR,
            item(self._active_profile_label, self._do_nothing, enabled=False),
            pystray.Menu.SEPARATOR,
            item("⚙  Settings", self._open_settings, default=True),
            item("🧹 Clear History", self._clear_history),
            pystray.Menu.SEPARATOR,
            item("✖  Quit ClipDrop", self._quit),
        )

        # Create the tray icon object
        self.tray = pystray.Icon(
            name="ClipDrop",
            icon=self.icon_image,
            title="ClipDrop",   # Tooltip shown when hovering over the icon
            menu=self.menu
        )


    def start(self):
        """
        Starts the tray icon and keeps the app running.
        This is a blocking call — the app stays alive here
        until the user clicks Quit from the tray menu.
        """
        print("Tray icon started. ClipDrop is running.")
        self.tray.run()  # This blocks until quit is called


    def stop(self):
        """Stops the tray icon and exits the app."""
        self.tray.stop()


    # ============================================================
    # MENU ACTIONS
    # ============================================================

    def _active_profile_label(self, item):
        """
        Returns the active profile name for display in the tray menu.
        Called dynamically by pystray each time the menu opens,
        so it always shows the current profile.
        """
        try:
            name = self.profiles.get_active_profile()["name"]
            return f"Profile: {name}"
        except Exception:
            return "Profile: General"


    def _open_settings(self, icon, menu_item):
        """
        Opens the Settings panel on the main tkinter thread.
        Toplevel windows must be created on the same thread as tk.Tk().
        """
        def open_on_main():
            from settings_panel import SettingsPanel
            panel = SettingsPanel(self.history, self.profiles, tk_root=self.root)
            panel.show()

        self.root.after(0, open_on_main)


    def _clear_history(self, icon, menu_item):
        """
        Clears all clipboard history when the user clicks
        'Clear History' in the tray menu.
        """
        self.history.clear_all()
        print("History cleared from tray menu.")

        # Show a brief notification in the tray
        self.tray.notify(
            title="ClipDrop",
            message="Clipboard history has been cleared."
        )


    def _quit(self, icon, menu_item):
        """
        Cleanly quits ClipDrop when the user clicks 'Quit'.
        Stops the tray icon and destroys the tkinter root.
        """
        print("Quitting ClipDrop...")
        self.tray.stop()
        self.root.after(0, self.root.destroy)


    def _do_nothing(self, icon, menu_item):
        """
        A placeholder action for non-clickable menu items
        like the app name header at the top of the menu.
        """
        pass


    # ============================================================
    # ICON LOADING
    # ============================================================

    def _load_icon(self):
        """
        Loads the ClipDrop icon from the assets folder.
        If no icon file is found, it generates a simple
        placeholder icon automatically so the app still works.
        """
        if os.path.exists(ICON_PATH):
            # Load the real icon from assets/icon.png
            return Image.open(ICON_PATH)
        else:
            # No icon file found — generate a simple one
            print("No icon found in assets/. Using generated placeholder icon.")
            return self._generate_placeholder_icon()


    def _generate_placeholder_icon(self):
        """
        Generates a simple clipboard-shaped icon as a placeholder.
        This is used when no icon.png exists in the assets folder.
        It draws a blue square with the letters 'CD' on it.
        """
        # Create a 64x64 pixel image with a blue background
        size = 64
        image = Image.new("RGBA", (size, size), color=(0, 0, 0, 0))
        draw = ImageDraw.Draw(image)

        # Draw a rounded blue rectangle as the background
        draw.rounded_rectangle(
            [4, 4, size - 4, size - 4],
            radius=12,
            fill=(79, 70, 229)  # Indigo/purple colour
        )

        # Draw the letters "CD" in white in the centre
        draw.text(
            (size // 2, size // 2),
            "CD",
            fill=(255, 255, 255),
            anchor="mm"  # Centre the text
        )

        return image
