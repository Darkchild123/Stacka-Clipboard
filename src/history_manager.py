# ============================================================
# Stacka - history_manager.py
# ============================================================
# This is the brain of Stacka. It manages everything related
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
    "history_limit": 50,   # How many items to keep by default
    "theme":         "dark",  # "dark" or "light"
    "transparency":  1.0      # Popup opacity: 0.5 (very see-through) to 1.0 (solid)
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


    def add_existing(self, item):
        """
        Insert an ALREADY-FORMED item as a new General entry — used when a clip
        is sent to General from a named profile.

        A profile keeps INDEPENDENT copies (export model), so a profile clip
        can outlive its General original (which ages out of the size limit).
        Sending it to General must therefore ADD it, not just un-hide.

        Unlike add_item (which saves a raw PIL image), the image content here
        is a FILE PATH, so it's COPIED into General's own images folder to
        survive the source profile later being deleted. If the item is already
        in General it's simply un-hidden (deduped).
        """
        import shutil
        import copy as _copy

        existing = self._find_by_id(item["id"])
        if existing is not None:
            if existing.get("hidden"):
                existing["hidden"] = False
                self._save_history()
            return

        it = _copy.deepcopy(item)
        it.pop("hidden", None)
        it["pinned"] = False
        if it.get("type") == "image":
            src = it.get("content")
            if src and os.path.exists(src):
                dst = os.path.join(IMAGES_DIR, f"{it['id']}.png")
                try:
                    if os.path.abspath(src) != os.path.abspath(dst):
                        shutil.copy2(src, dst)
                    it["content"] = dst
                except Exception as e:
                    print(f"Failed to copy image into General: {e}")

        self.items.insert(0, it)
        self._enforce_limit()
        self._save_history()


    # ============================================================
    # GETTING ITEMS
    # ============================================================

    def get_all(self):
        """
        Returns all visible items in display order: pinned first, then rest.
        Items with hidden=True (auto-created side-panel entries) are excluded
        so they never appear in the General clipboard list.
        """
        visible  = [i for i in self.items if not i.get("hidden")]
        pinned   = [i for i in visible if i.get("pinned")]
        unpinned = [i for i in visible if not i.get("pinned")]
        return pinned + unpinned

    def get_all_including_hidden(self):
        """
        Returns every item regardless of hidden flag.
        Used by ProfileManager so hidden auto-created entries still appear
        in named profiles they have been assigned to.
        """
        pinned   = [i for i in self.items if i.get("pinned")]
        unpinned = [i for i in self.items if not i.get("pinned")]
        return pinned + unpinned


    def get_preview(self, item):
        """
        Returns a short preview string for an item to show in the dropdown.
        - Text: first 60 characters
        - File: file name(s)
        - Image: "📷 Image"
        """
        if item["type"] == "card":
            # NEVER the real number — the masked form only. The full PAN lives
            # encrypted in item["content"]; brand/last4 are the safe cleartext.
            brand = item.get("brand", "Card")
            last4 = item.get("last4", "••••")
            return f"{brand} •••• {last4}"

        if item["type"] == "url":
            url = item["content"].strip()
            return url[:120] + "..." if len(url) > 120 else url

        if item["type"] in ("code", "bash"):
            import re
            # Show the first non-empty line as the preview
            first_line = next(
                (l.strip() for l in item["content"].splitlines() if l.strip()), ""
            )
            return first_line[:120] + "..." if len(first_line) > 120 else first_line

        if item["type"] == "text":
            # Strip leading/trailing whitespace so the preview always starts
            # with real characters, not blank lines from how text was selected.
            # Also collapse internal newlines/tabs into a single space so
            # multi-line copies display as one readable line in the dropdown.
            import re
            text = item["content"].strip()
            text = re.sub(r"\s+", " ", text)
            return text[:120] + "..." if len(text) > 120 else text

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

    def remove_file_from_item(self, item_id, filepath):
        """
        Removes one file path from a multi-file clipboard entry's content list.
        If the entry becomes empty afterwards the whole entry is deleted.
        Returns True if the entry still exists, False if it was fully removed.
        """
        item = self._find_by_id(item_id)
        if item is None:
            return True
        if isinstance(item.get("content"), list) and filepath in item["content"]:
            item["content"].remove(filepath)
            if not item["content"]:
                self.items.remove(item)
                self._save_history()
                return False
        self._save_history()
        return True


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


    def save_setting(self, key, value):
        """
        Saves a single setting by key.
        Used by the Settings panel for theme, transparency, etc.
        """
        self.settings[key] = value
        self._save_settings()
        print(f"Setting saved: {key} = {value}")


    # ============================================================
    # INTERNAL HELPERS (private methods — used only inside this file)
    # ============================================================

    def _ensure_folders(self):
        """Makes sure all the folders Stacka needs actually exist."""
        os.makedirs(DATA_DIR,     exist_ok=True)
        os.makedirs(SETTINGS_DIR, exist_ok=True)
        os.makedirs(IMAGES_DIR,   exist_ok=True)

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
        Saves the current history list to history.json using an atomic write.

        Writes to a .tmp file first, then os.replace() atomically promotes it.
        A .bak copy is kept so _load_history() can recover from corruption.
        """
        try:
            tmp_path = HISTORY_FILE + ".tmp"
            bak_path = HISTORY_FILE + ".bak"

            with open(tmp_path, "w", encoding="utf-8") as f:
                json.dump(self.items, f, indent=2, ensure_ascii=False)
                f.flush()
                os.fsync(f.fileno())

            if os.path.exists(HISTORY_FILE):
                try:
                    import shutil
                    shutil.copy2(HISTORY_FILE, bak_path)
                except Exception:
                    pass

            os.replace(tmp_path, HISTORY_FILE)

        except Exception as e:
            print(f"Failed to save history: {e}")


    def _load_history(self):
        """
        Loads history from history.json.
        Falls back to history.json.bak if the main file is corrupt.
        """
        bak_path = HISTORY_FILE + ".bak"

        for path in [HISTORY_FILE, bak_path]:
            if not os.path.exists(path):
                continue
            try:
                with open(path, "r", encoding="utf-8") as f:
                    data = json.load(f)
                if path == bak_path:
                    print("History recovered from backup.")
                return data
            except Exception as e:
                print(f"Failed to load history from {os.path.basename(path)}: {e}")

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
        Falls back to DEFAULT_SETTINGS if the file is missing or unreadable.
        """
        if os.path.exists(SETTINGS_FILE):
            try:
                with open(SETTINGS_FILE, "r", encoding="utf-8") as f:
                    data = json.load(f)
                # Merge with defaults so new keys are always present
                merged = dict(DEFAULT_SETTINGS)
                merged.update(data)
                return merged
            except Exception as e:
                print(f"Failed to load settings: {e}")
        return dict(DEFAULT_SETTINGS)
