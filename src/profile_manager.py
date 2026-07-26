# ============================================================
# Stacka - profile_manager.py
# ============================================================
# Manages clipboard profiles — named collections that let users
# organise their clipboard history into separate workflows.
#
# There is always one built-in profile called "General" that
# shows the full live clipboard history and cannot be deleted.
#
# STORAGE MODEL — EXPORT / COPY (not references):
#   Sending an item to a named profile stores an INDEPENDENT COPY of it in
#   that profile. Profiles do NOT reference the shared history pool, so an
#   item aging out of General (or any profile) due to the size limit — or
#   being deleted there — never affects the same item held by another
#   profile. Each profile owns its items and trims them itself.
#
#   General            → the live history (HistoryManager); size-limited there.
#   Named profile      → its own list of item copies, trimmed to the SAME
#                        universal size limit, independently.
#
#   Image items are binary, so each profile keeps its OWN copy of the PNG
#   under data/images/profiles/<profile_id>/ — deleting a profile's copy
#   never touches General's image or another profile's.
# ============================================================

import json
import os
import copy
import shutil
import uuid


import secure_store
from app_paths import user_data_root
BASE_DIR      = user_data_root()
DATA_DIR      = os.path.join(BASE_DIR, "data")
PROFILES_FILE = os.path.join(DATA_DIR, "profiles.json")
# Per-profile image copies live here, one sub-folder per profile id.
PROFILE_IMAGES_DIR = os.path.join(DATA_DIR, "images", "profiles")

GENERAL_ID = "general"   # Reserved ID for the built-in General profile


class ProfileManager:

    def __init__(self, history_manager):
        """
        history_manager — the shared HistoryManager instance. General reads
        its live items from it; named profiles keep their own copies and only
        use it for the universal size-limit value (get_limit).
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

        General      → the live history (already excludes hidden entries).
        Named profile → this profile's OWN copies, newest first, with
                        profile-pinned items floated to the top.
        """
        profile = self.get_active_profile()

        if profile["id"] == GENERAL_ID:
            return self.history.get_all()   # already excludes hidden

        # Own copies are stored newest-first (each export inserts at index 0).
        items  = list(profile.get("items", []))
        pinned = set(profile.get("pinned_item_ids", []))
        # Stable sort keeps recency order within each group; pinned float up.
        items.sort(key=lambda x: 0 if x["id"] in pinned else 1)
        return items


    def get_profile_item_count(self, profile_id):
        """Returns how many items a profile currently contains."""
        if profile_id == GENERAL_ID:
            return len(self.history.get_all())
        profile = self._find(profile_id)
        return len(profile.get("items", [])) if profile else 0


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
            "id":              new_id,
            "name":            name.strip(),
            "built_in":        False,
            "items":           [],   # own copies (export model)
            "pinned_item_ids": [],
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
        Deletes a user profile (and its copied image files).
        The General profile cannot be deleted.
        If the deleted profile was active, switches back to General.
        """
        if profile_id == GENERAL_ID:
            return
        self.profiles = [p for p in self.profiles if p["id"] != profile_id]
        self._delete_profile_images(profile_id)
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
    # PER-PROFILE PIN STATE
    # ============================================================

    def toggle_pin_in_profile(self, item_id, profile_id):
        """
        Pins or unpins an item within a named profile only.
        This is independent of the item's global pin state in history.
        The General profile does not have per-profile pins —
        it always uses the item's global pinned flag.
        """
        if profile_id == GENERAL_ID:
            return
        profile = self._find(profile_id)
        if not profile:
            return
        pinned = profile.setdefault("pinned_item_ids", [])
        if item_id in pinned:
            pinned.remove(item_id)
            status = "unpinned"
        else:
            pinned.append(item_id)
            status = "pinned"
        self._save()
        print(f"Item {item_id} {status} in profile {profile_id}")

    def is_pinned_in_profile(self, item_id, profile_id):
        """Returns True if the item is pinned within this specific profile."""
        if profile_id == GENERAL_ID:
            return False   # General uses the item's global pinned flag
        profile = self._find(profile_id)
        if not profile:
            return False
        return item_id in profile.get("pinned_item_ids", [])

    # ============================================================
    # ASSIGNING ITEMS TO PROFILES  (export a copy)
    # ============================================================

    def add_item_to_profile(self, item, profile_id):
        """
        Export a COPY of `item` into a named profile. The copy is fully
        independent of General and of any other profile. Re-exporting an item
        already in the profile just moves it back to the top (dedupe by id).
        Then the profile is trimmed to the universal size limit.

        `item` is the full item dict (not just an id) so the profile can own
        a self-contained copy even after the original ages out of General.
        """
        if profile_id == GENERAL_ID:
            return
        profile = self._find(profile_id)
        if not profile:
            return
        items = profile.setdefault("items", [])
        iid   = item["id"]
        # Drop any existing copy first (dedupe / move-to-top) and its image.
        for existing in [x for x in items if x["id"] == iid]:
            items.remove(existing)
            self._delete_item_image(existing, profile_id)
        items.insert(0, self._copy_item_for_profile(item, profile_id))
        self._enforce_profile_limit(profile)
        self._save()


    def remove_item_from_profile(self, item_id, profile_id):
        """Removes an item's copy from a specific profile (and its pin)."""
        profile = self._find(profile_id)
        if not profile:
            return
        items = profile.get("items", [])
        for existing in [x for x in items if x["id"] == item_id]:
            items.remove(existing)
            self._delete_item_image(existing, profile_id)
        pinned = profile.get("pinned_item_ids", [])
        if item_id in pinned:
            pinned.remove(item_id)
        self._save()


    def clear_profile(self, profile_id, keep_pinned: bool = False):
        """
        Removes all items from a named profile (and their copied images).
        General cannot be cleared this way — use history.clear_all() instead.

        keep_pinned=True spares items pinned IN THIS PROFILE (auto-wipe).
        """
        if profile_id == GENERAL_ID:
            return
        profile = self._find(profile_id)
        if not profile:
            return
        pinned_ids = set(profile.get("pinned_item_ids", [])) if keep_pinned else set()
        kept = []
        for it in profile.get("items", []):
            if it["id"] in pinned_ids:
                kept.append(it)
            else:
                self._delete_item_image(it, profile_id)
        profile["items"] = kept
        profile["pinned_item_ids"] = [i for i in profile.get("pinned_item_ids", [])
                                      if any(k["id"] == i for k in kept)]
        self._save()
        print(f"Profile cleared: {profile_id} ({len(kept)} pinned kept)")


    def clear_all_profiles(self, keep_pinned: bool = False):
        """Clear every NAMED profile. General is the live history and is
        cleared through HistoryManager.clear_all() by the caller."""
        n = 0
        for p in list(self.profiles):
            if p["id"] == GENERAL_ID or p.get("built_in"):
                continue
            self.clear_profile(p["id"], keep_pinned=keep_pinned)
            n += 1
        return n


    def remove_item_from_all(self, item_id):
        """
        Removes an item's copy from every named profile. Rarely needed in the
        export model (deleting in one place no longer affects others) — kept
        for callers that want to purge an id everywhere at once.
        """
        changed = False
        for profile in self.profiles:
            if profile.get("built_in"):
                continue
            items = profile.get("items", [])
            for existing in [x for x in items if x["id"] == item_id]:
                items.remove(existing)
                self._delete_item_image(existing, profile["id"])
                changed = True
            pinned = profile.get("pinned_item_ids", [])
            if item_id in pinned:
                pinned.remove(item_id)
                changed = True
        if changed:
            self._save()


    def get_item_profiles(self, item_id):
        """Returns a list of named-profile IDs that hold a copy of this item."""
        return [
            p["id"] for p in self.profiles
            if not p.get("built_in")
            and any(x["id"] == item_id for x in p.get("items", []))
        ]

    def move_item_up(self, item_id, profile_id):
        """Reorder an item one slot toward the top WITHIN this profile only —
        never touches General or another profile (own copies)."""
        self._move_item(item_id, profile_id, -1)

    def move_item_down(self, item_id, profile_id):
        self._move_item(item_id, profile_id, +1)

    def _move_item(self, item_id, profile_id, delta):
        if profile_id == GENERAL_ID:
            return
        profile = self._find(profile_id)
        if not profile:
            return
        items = profile.get("items", [])
        idx = next((i for i, x in enumerate(items) if x["id"] == item_id), -1)
        j = idx + delta
        if idx >= 0 and 0 <= j < len(items):
            items[idx], items[j] = items[j], items[idx]
            self._save()


    # ============================================================
    # SIZE LIMIT  (universal value, enforced per profile)
    # ============================================================

    def enforce_all_limits(self):
        """Re-trim every named profile to the current universal limit.
        Call after the size limit changes in Settings."""
        changed = False
        for p in self.profiles:
            if p.get("built_in"):
                continue
            if self._enforce_profile_limit(p):
                changed = True
        if changed:
            self._save()

    def _enforce_profile_limit(self, profile):
        """Trim a profile's own items to the universal limit, oldest UNPINNED
        first (pinned copies are never auto-removed). Returns True if anything
        was removed. Does NOT save — the caller decides when to persist."""
        limit  = self.history.get_limit()
        items  = profile.get("items", [])
        pinned = set(profile.get("pinned_item_ids", []))
        removed_any = False
        while len(items) > limit:
            # Oldest = end of the list (newest is inserted at index 0).
            idx = next((i for i in range(len(items) - 1, -1, -1)
                        if items[i]["id"] not in pinned), None)
            if idx is None:
                break   # everything left is pinned — stop
            removed = items.pop(idx)
            self._delete_item_image(removed, profile["id"])
            removed_any = True
        return removed_any


    # ============================================================
    # PER-PROFILE ITEM COPIES  (helpers)
    # ============================================================

    def _copy_item_for_profile(self, item, profile_id):
        """Deep-copy an item for independent storage in a profile. Image
        items get their OWN copy of the PNG so the profile fully owns it."""
        it = copy.deepcopy(item)
        it.pop("hidden", None)      # a profile copy is a real, shown entry
        if it.get("type") == "image":
            src = it.get("content")
            if src and os.path.exists(src):
                try:
                    dst_dir = os.path.join(PROFILE_IMAGES_DIR, profile_id)
                    os.makedirs(dst_dir, exist_ok=True)
                    dst = os.path.join(dst_dir, f"{it['id']}.png")
                    shutil.copy2(src, dst)
                    it["content"] = dst
                except Exception as e:
                    print(f"Failed to copy image for profile: {e}")
        return it

    def _delete_item_image(self, item, profile_id):
        """Delete a profile copy's image file — but ONLY if it actually lives
        under this profile's own image folder, so we can never delete
        General's shared image or another profile's copy."""
        if item.get("type") != "image":
            return
        path = item.get("content")
        if not path or not os.path.exists(path):
            return
        prof_dir = os.path.abspath(os.path.join(PROFILE_IMAGES_DIR, profile_id))
        try:
            if os.path.commonpath([os.path.abspath(path), prof_dir]) == prof_dir:
                os.remove(path)
        except Exception:
            pass

    def _delete_profile_images(self, profile_id):
        """Remove a profile's entire image-copy folder (on profile delete)."""
        d = os.path.join(PROFILE_IMAGES_DIR, profile_id)
        if os.path.isdir(d):
            shutil.rmtree(d, ignore_errors=True)


    # ============================================================
    # PERSISTENCE
    # ============================================================

    def _save(self):
        """
        Saves all profile data to profiles.json using an atomic write.

        Strategy: write to a .tmp file first, then os.replace() it into place.
        os.replace() is atomic on both Windows and Linux, so a crash or
        interruption during the write can never leave profiles.json in a
        half-written (corrupt) state.  A backup copy (.bak) is also kept so
        _load() can recover from any remaining edge-case corruption.
        """
        os.makedirs(DATA_DIR, exist_ok=True)
        payload = {"active_id": self.active_id, "profiles": self.profiles}
        # Encrypted at rest (DPAPI) with the same atomic .tmp → .bak →
        # os.replace strategy. See secure_store.py.
        secure_store.write_json(PROFILES_FILE, payload)


    def _load(self):
        """
        Loads profile data from profiles.json.

        Recovery order:
          1. Try profiles.json  (the live file)
          2. Try profiles.json.bak (the last known-good backup)
          3. Fall back to a fresh General-only default

        Any profile still in the OLD reference format (item_ids) is migrated
        to the export/copy format on first load.
        """
        bak_path = PROFILES_FILE + ".bak"

        for path in [PROFILES_FILE, bak_path]:
            if not os.path.exists(path):
                continue
            try:
                data = secure_store.read_json(path)
                if data is None:
                    raise ValueError("unreadable")

                self.profiles = data.get("profiles", self._default_profiles())
                saved_id      = data.get("active_id", GENERAL_ID)

                # Always ensure General exists as the first entry
                if not any(p["id"] == GENERAL_ID for p in self.profiles):
                    self.profiles.insert(0, self._general_profile())

                # Old reference format → own-copy format
                self._migrate_refs_to_copies()

                # Restore the last active profile only if it still has items.
                saved_profile = self._find(saved_id)
                if (saved_id == GENERAL_ID or
                        (saved_profile and saved_profile.get("items"))):
                    self.active_id = saved_id
                else:
                    self.active_id = GENERAL_ID
                    print(f"Last profile '{saved_id}' is empty — reverting to General.")

                if path == bak_path:
                    print("Profiles recovered from backup — re-saving clean copy.")
                    self._save()
                return

            except Exception as e:
                print(f"Failed to load profiles from {os.path.basename(path)}: {e}")

        # Both files unreadable — start fresh
        print("No readable profile file found — creating defaults.")
        self.profiles  = self._default_profiles()
        self.active_id = GENERAL_ID
        self._save()


    def _migrate_refs_to_copies(self):
        """One-time upgrade: turn each named profile's item_ids (references
        into the shared history pool) into self-contained item copies. Items
        already gone from history can't be recovered and are dropped."""
        changed = False
        for p in self.profiles:
            if p.get("built_in"):
                if p.pop("item_ids", None) is not None:
                    changed = True
                p.setdefault("pinned_item_ids", [])
                continue
            if "item_ids" not in p:
                p.setdefault("items", [])
                p.setdefault("pinned_item_ids", [])
                continue
            old_ids = p.get("item_ids", [])
            copies  = []
            for iid in old_ids:
                src = self.history._find_by_id(iid)
                if src is not None:
                    copies.append(self._copy_item_for_profile(src, p["id"]))
            p["items"] = copies
            p.pop("item_ids", None)
            p.setdefault("pinned_item_ids", [])
            changed = True
        if changed:
            self._save()

    # ============================================================
    # INTERNAL HELPERS
    # ============================================================

    def _default_profiles(self):
        return [self._general_profile()]

    def _general_profile(self):
        return {"id": GENERAL_ID, "name": "General", "built_in": True,
                "pinned_item_ids": []}

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
