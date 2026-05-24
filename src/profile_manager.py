# ============================================================
# ClipDrop - profile_manager.py
# ============================================================
# Manages clipboard profiles — named collections that let users
# organise their clipboard history into separate workflows.
#
# There is always one built-in profile called "General" that
# shows the full clipboard history and cannot be deleted.
# User-created profiles are named collections of item IDs
# that reference items from the shared history pool.
# The same item can belong to multiple profiles at once.
# ============================================================

import json
import os
import uuid


BASE_DIR      = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DATA_DIR      = os.path.join(BASE_DIR, "data")
PROFILES_FILE = os.path.join(DATA_DIR, "profiles.json")

GENERAL_ID = "general"   # Reserved ID for the built-in General profile


class ProfileManager:

    def __init__(self, history_manager):
        """
        history_manager — the shared HistoryManager instance.
        ProfileManager reads items from it but never writes to it.
        """
        self.history  = history_manager
        self.profiles = []          # Ordered list of profile dicts
        self.active_id = GENERAL_ID # ID of the currently active profile
        self._load()
        print(f"Profiles loaded: {len(self.profiles)} profiles.")


    # ============================================================
    # READING
    # ============================================================

    def get_all_profiles(self):
        """Returns all profiles in display order."""
        return list(self.profiles)


    def get_active_profile(self):
        """Returns the currently active profile dict."""
        for p in self.profiles:
            if p["id"] == self.active_id:
                return p
        # Fallback — active profile was deleted; reset to General
        self.active_id = GENERAL_ID
        return self.profiles[0]


    def get_active_items(self):
        """
        Returns the clipboard items to display for the active profile.

        General  → all items from history (no filtering)
        Any other profile → only items whose IDs are listed in the
                            profile's item_ids, in history order.
                            Orphaned IDs (deleted items) are skipped.
        """
        profile   = self.get_active_profile()
        all_items = self.history.get_all()

        if profile["id"] == GENERAL_ID:
            return all_items

        id_set = set(profile.get("item_ids", []))
        return [item for item in all_items if item["id"] in id_set]


    def get_profile_item_count(self, profile_id):
        """Returns how many (live) items a profile currently contains."""
        if profile_id == GENERAL_ID:
            return len(self.history.get_all())

        all_ids   = {item["id"] for item in self.history.get_all()}
        profile   = self._find(profile_id)
        if not profile:
            return 0
        return sum(1 for iid in profile.get("item_ids", []) if iid in all_ids)


    # ============================================================
    # SWITCHING
    # ============================================================

    def set_active(self, profile_id):
        """Switches the active profile."""
        if any(p["id"] == profile_id for p in self.profiles):
            self.active_id = profile_id
            self._save()
            print(f"Active profile switched to: {profile_id}")


    # ============================================================
    # CREATING / EDITING PROFILES
    # ============================================================

    def create_profile(self, name):
        """
        Creates a new user profile with a unique ID.
        Returns the new profile's ID.
        """
        new_id  = str(uuid.uuid4())[:8]
        profile = {
            "id":       new_id,
            "name":     name.strip(),
            "built_in": False,
            "item_ids": []
        }
        self.profiles.append(profile)
        self._save()
        print(f"Profile created: '{name}' (id={new_id})")
        return new_id


    def rename_profile(self, profile_id, new_name):
        """Renames a user profile. Built-in profiles cannot be renamed."""
        profile = self._find(profile_id)
        if profile and not profile.get("built_in"):
            profile["name"] = new_name.strip()
            self._save()


    def delete_profile(self, profile_id):
        """
        Deletes a user profile.
        The General profile cannot be deleted.
        If the deleted profile was active, switches back to General.
        """
        if profile_id == GENERAL_ID:
            return
        self.profiles = [p for p in self.profiles if p["id"] != profile_id]
        if self.active_id == profile_id:
            self.active_id = GENERAL_ID
        self._save()
        print(f"Profile deleted: {profile_id}")


    def move_up(self, profile_id):
        """Moves a profile one position up. General always stays first."""
        idx = self._index_of(profile_id)
        if idx > 1:   # idx 0 is always General — can't move above it
            self.profiles[idx], self.profiles[idx - 1] = \
                self.profiles[idx - 1], self.profiles[idx]
            self._save()


    def move_down(self, profile_id):
        """Moves a profile one position down."""
        idx = self._index_of(profile_id)
        if 0 < idx < len(self.profiles) - 1:
            self.profiles[idx], self.profiles[idx + 1] = \
                self.profiles[idx + 1], self.profiles[idx]
            self._save()


    # ============================================================
    # ASSIGNING ITEMS TO PROFILES
    # ============================================================

    def add_item_to_profile(self, item_id, profile_id):
        """Adds an item to a profile. Ignores duplicates."""
        profile = self._find(profile_id)
        if profile and profile_id != GENERAL_ID:
            ids = profile.setdefault("item_ids", [])
            if item_id not in ids:
                ids.append(item_id)
                self._save()


    def remove_item_from_profile(self, item_id, profile_id):
        """Removes an item from a specific profile."""
        profile = self._find(profile_id)
        if profile and item_id in profile.get("item_ids", []):
            profile["item_ids"].remove(item_id)
            self._save()


    def remove_item_from_all(self, item_id):
        """
        Removes an item from every profile.
        Call this when an item is deleted from history so no
        profile holds a reference to a non-existent item.
        """
        for profile in self.profiles:
            if item_id in profile.get("item_ids", []):
                profile["item_ids"].remove(item_id)
        self._save()


    def get_item_profiles(self, item_id):
        """Returns a list of profile IDs that contain this item."""
        return [
            p["id"] for p in self.profiles
            if item_id in p.get("item_ids", [])
        ]


    # ============================================================
    # PERSISTENCE
    # ============================================================

    def _save(self):
        """Saves all profile data to profiles.json."""
        try:
            os.makedirs(DATA_DIR, exist_ok=True)
            with open(PROFILES_FILE, "w", encoding="utf-8") as f:
                json.dump(
                    {"active_id": self.active_id, "profiles": self.profiles},
                    f, indent=2, ensure_ascii=False
                )
        except Exception as e:
            print(f"Failed to save profiles: {e}")


    def _load(self):
        """Loads profile data from profiles.json. Creates defaults if missing."""
        if not os.path.exists(PROFILES_FILE):
            self.profiles  = self._default_profiles()
            self.active_id = GENERAL_ID
            self._save()
            return
        try:
            with open(PROFILES_FILE, "r", encoding="utf-8") as f:
                data = json.load(f)
            self.profiles  = data.get("profiles", self._default_profiles())
            self.active_id = data.get("active_id", GENERAL_ID)

            # Always ensure General exists as the first entry
            if not any(p["id"] == GENERAL_ID for p in self.profiles):
                self.profiles.insert(0, self._general_profile())

        except Exception as e:
            print(f"Failed to load profiles: {e}")
            self.profiles  = self._default_profiles()
            self.active_id = GENERAL_ID


    # ============================================================
    # INTERNAL HELPERS
    # ============================================================

    def _default_profiles(self):
        return [self._general_profile()]

    def _general_profile(self):
        return {"id": GENERAL_ID, "name": "General", "built_in": True, "item_ids": []}

    def _find(self, profile_id):
        for p in self.profiles:
            if p["id"] == profile_id:
                return p
        return None

    def _index_of(self, profile_id):
        for i, p in enumerate(self.profiles):
            if p["id"] == profile_id:
                return i
        return -1
