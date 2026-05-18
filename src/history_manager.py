# ============================================================
# ClipDrop - history_manager.py
# ============================================================
# This is the brain of ClipDrop. It manages everything related
# to clipboard history — saving, loading, pinning, deleting,
# reordering, and enforcing the history size limit.
# ============================================================

import json
import os
import uuid
from PIL import Image


# --- File paths for saving data ---
# os.path.dirname(__file__) means "the folder this file is in" (src/)
# We then go one level up (..) to reach the project root
BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DATA_DIR = os.path.join(BASE_DIR, "data")
SETTINGS_DIR = os.path.join(BASE_DIR, "settings")
HISTORY_FILE = os.path.join(DATA_DIR, "history.json")
SETTINGS_FILE = os.path.join(SETTINGS_DIR, "config.json")
IMAGES_DIR = os.path.join(DATA_DIR, "images")

# Default settings
DEFAULT_SETTINGS = {
    "history_limit": 50  # How many items to keep by default
}


class HistoryManager:

    def __init__(self):
        # Make sure all necessary folders exist
        self._ensure_folders()

        # Load settings (e.g. history size limit)
        self.settings = self._load_settings()

        # Load previously saved history from disk
        # self.items is a list — an ordered collection of clipboard items
        self.items = self._load_history()

        print(f"History loaded: {len(self.items)} items.")


    # ============================================================
    # ADDING ITEMS
    # ============================================================

    def add_item(self, item):
        """
        Adds a new clipboard item to the history.
        If the item already exists, it moves it to the top instead
        of creating a duplicate.
        """
        # Check if this item already exists in history
        existing = self._find_by_id(item["id"])

        if existing is not None:
            # Item already exists — remove it from its current position
            self.items.remove(existing)

            # If it was pinned before, keep it pinned
            item["pinned"] = existing.get("pinned", False)

        # If it's an image, save the image file to disk
        # and store the file path instead (images can't go in JSON)
        if item["type"] == "image":
            image_path = self._save_image(item["content"], item["id"])
            if image_path is None:
                return  # If image saving failed, skip this item
            item["content"] = image_path  # Store the path, not the image itself

        # Add the item at the top of the list (index 0 = top)
        self.items.insert(0, item)

        # Enforce the history size limit
        self._enforce_limit()

        # Save updated history to disk
        self._save_history()


    # ============================================================
    # GETTING ITEMS
    # ============================================================

    def get_all(self):
        """
        Returns all items in the correct display order:
        Pinned items first (in their order), then the rest.
        """
        pinned = [item for item in self.items if item.get("pinned")]
        unpinned = [item for item in self.items if not item.get("pinned")]
        return pinned + unpinned


    def get_preview(self, item):
        """
        Returns a short preview string for an item to show in the dropdown.
        - Text: first 60 characters
        - File: file name(s)
        - Image: "📷 Image"
        """
        if item["type"] == "text":
            text = item["content"]
            return text[:60] + "..." if len(text) > 60 else text

        elif item["type"] == "file":
            files = item["content"]
            if isinstance(files, list):
                names = [os.path.basename(f) for f in files]
                return ", ".join(names)
            return str(files)

        elif item["type"] == "image":
            return "📷 Image"

        return "Unknown item"


    # ============================================================
    # PIN / UNPIN
    # ============================================================

    def toggle_pin(self, item_id):
        """
        Pins an item if it's not pinned, unpins it if it is.
        Pinned items always stay at the top of the list.
        """
        item = self._find_by_id(item_id)
        if item:
            item["pinned"] = not item.get("pinned", False)
            self._save_history()
            status = "pinned" if item["pinned"] else "unpinned"
            print(f"Item {item_id} {status}.")


    # ============================================================
    # DELETE
    # ============================================================

    def delete_item(self, item_id):
        """
        Removes an item from history permanently.
        If it was an image, also deletes the saved image file.
        """
        item = self._find_by_id(item_id)
        if item:
            # If it's an image, delete the saved image file too
            if item["type"] == "image" and os.path.exists(item["content"]):
                os.remove(item["content"])

            self.items.remove(item)
            self._save_history()
            print(f"Item {item_id} deleted.")


    # ============================================================
    # REORDER (Move Up / Move Down)
    # ============================================================

    def move_up(self, item_id):
        """
        Moves an item one position up in the list.
        Pinned items cannot be moved — they stay at the top.
        """
        item = self._find_by_id(item_id)
        if item and not item.get("pinned"):
            index = self.items.index(item)
            if index > 0:
                # Swap the item with the one above it
                self.items[index], self.items[index - 1] = \
                    self.items[index - 1], self.items[index]
                self._save_history()


    def move_down(self, item_id):
        """
        Moves an item one position down in the list.
        Pinned items cannot be moved.
        """
        item = self._find_by_id(item_id)
        if item and not item.get("pinned"):
            index = self.items.index(item)
            if index < len(self.items) - 1:
                # Swap the item with the one below it
                self.items[index], self.items[index + 1] = \
                    self.items[index + 1], self.items[index]
                self._save_history()


    # ============================================================
    # CLEAR ALL
    # ============================================================

    def clear_all(self):
        """
        Deletes all clipboard history.
        Also cleans up any saved image files.
        """
        # Delete all saved image files
        for item in self.items:
            if item["type"] == "image" and os.path.exists(item["content"]):
                os.remove(item["content"])

        # Clear the list
        self.items = []
        self._save_history()
        print("History cleared.")


    # ============================================================
    # SETTINGS
    # ============================================================

    def get_limit(self):
        """Returns the current history size limit."""
        return self.settings.get("history_limit", 50)


    def set_limit(self, new_limit):
        """
        Updates the history size limit and saves it.
        Also trims the history if it's now over the new limit.
        """
        self.settings["history_limit"] = new_limit
        self._save_settings()
        self._enforce_limit()
        self._save_history()
        print(f"History limit set to {new_limit}.")


    # ============================================================
    # INTERNAL HELPERS (private methods — used only inside this file)
    # ============================================================

    def _find_by_id(self, item_id):
        """
        Searches the history list for an item with a matching ID.
        Returns the item if found, or None if not found.
        """
        for item in self.items:
            if item["id"] == item_id:
                return item
        return None


    def _enforce_limit(self):
        """
        Makes sure the history doesn't exceed the size limit.
        It always removes the oldest UNPINNED items first —
        pinned items are never auto-removed.
        """
        limit = self.get_limit()

        while len(self.items) > limit:
            # Find the last unpinned item and remove it
            for i in range(len(self.items) - 1, -1, -1):
                if not self.items[i].get("pinned"):
                    removed = self.items.pop(i)
                    # Clean up image file if needed
                    if removed["type"] == "image" and os.path.exists(removed["content"]):
                        os.remove(removed["content"])
                    break
            else:
                # All remaining items are pinned — stop trimming
                break


    def _save_image(self, image, item_id):
        """
        Saves a PIL Image object to the images folder as a PNG file.
        Returns the file path, or None if saving failed.
        """
        try:
            filename = f"{item_id}.png"
            filepath = os.path.join(IMAGES_DIR, filename)
            image.save(filepath, format="PNG")
            return filepath
        except Exception as e:
            print(f"Failed to save image: {e}")
            return None


    def _save_history(self):
        """
        Saves the current history list to history.json on disk.
        JSON is a simple text format for storing structured data.
        """
        try:
            # We can't save PIL Image objects to JSON,
            # but by now images are stored as file paths (strings), so it's fine
            with open(HISTORY_FILE, "w", encoding="utf-8") as f:
                json.dump(self.items, f, indent=2, ensure_ascii=False)
        except Exception as e:
            print(f"Failed to save history: {e}")


    def _load_history(self):
        """
        Loads history from the history.json file on disk.
        If the file doesn't exist yet, returns an empty list.
        """
        if not os.path.exists(HISTORY_FILE):
            return []
        try:
            with open(HISTORY_FILE, "r", encoding="utf-8") as f:
                return json.load(f)
        except Exception as e:
            print(f"Failed to load history: {e}")
            return []


    def _save_settings(self):
        """Saves current settings to config.json."""
        try:
            with open(SETTINGS_FILE, "w", encoding="utf-8") as f:
                json.dump(self.settings, f, indent=2)
        except Exception as e:
            print(f"Failed to save settings: {e}")


    def _load_settings(self):
        """
        Loads settings from config.json.
        If the file doesn't exist, returns the default settings.
        """
        if not os.path.exists(SETTINGS_FILE):
            return DEFAULT_SETTINGS.copy()
        try:
            with open(SETTINGS_FILE, "r", encoding="utf-8") as f:
                return json.load(f)
        except Exception as e:
            print(f"Failed to load settings: {e}")
            return DEFAULT_SETTINGS.copy()


    def _ensure_folders(self):
        """
        Makes sure all the folders ClipDrop needs actually exist.
        If they don't, it creates them. This runs once at startup.
        """
        os.makedirs(DATA_DIR, exist_ok=True)
        os.makedirs(SETTINGS_DIR, exist_ok=True)
        os.makedirs(IMAGES_DIR, exist_ok=True)
