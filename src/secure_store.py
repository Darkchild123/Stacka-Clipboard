# ============================================================
# Stacka - secure_store.py
# ============================================================
# Encryption at rest for the clipboard stores (history.json,
# profiles.json).
#
# WHY: a clipboard manager persists everything you copy, so a stolen or
# snooped data file exposes far more than the live clipboard — passwords,
# tokens and other secrets people routinely copy. These files used to be
# plaintext JSON, guarded only by filesystem permissions.
#
# HOW: the JSON is encrypted with **Windows DPAPI**
# (CryptProtectData / CRYPTPROTECT_UI_FORBIDDEN) — the same mechanism the
# credit-card feature already uses. The key is derived and held by Windows
# and tied to the logged-in USER ACCOUNT, so:
#   * no password prompt — zero friction for the user
#   * the file is useless if copied to another machine or opened by
#     another Windows user
#
# WHAT IT DOES NOT DO (documented honestly): DPAPI cannot protect against
# malicious code already running AS the same Windows user — such code can
# ask Windows to decrypt, or simply read the live clipboard. It protects
# data AT REST (file theft, backups, other accounts, snooping), not a
# fully compromised, unlocked session.
#
# FORMAT: an encrypted file is itself a small JSON envelope, so it stays a
# valid text file and is trivially detectable:
#     {"stacka_enc": 1, "data": "<base64 DPAPI blob>"}
# A plaintext (legacy) file is the bare JSON payload as before.
#
# MIGRATION: read_json() accepts BOTH formats, so an existing plaintext
# history is loaded normally and simply rewritten encrypted on the next
# save. It also still reads envelopes stamped with the pre-rename key
# (see _LEGACY_ENVELOPE_KEYS). No user action, no data loss.
#
# FALLBACK: if DPAPI is unavailable (non-Windows, or the API fails),
# write_json() falls back to plaintext rather than losing the user's data,
# and says so once. Availability can be checked with is_encryption_available().
# ============================================================

import base64
import json
import os

_ENVELOPE_KEY = "stacka_enc"

# Files encrypted before the app was renamed carry the old stamp. Reading them
# must keep working — otherwise an existing encrypted history stops looking
# like an envelope, gets handed back as raw JSON, and the user's data is gone.
# They are re-stamped with the current key on the next save.
_LEGACY_ENVELOPE_KEYS = ("clipdrop_enc",)

_warned = False


def _envelope_blob(raw):
    """The base64 blob if `raw` is an encrypted envelope (current or legacy
    stamp), else None."""
    if not isinstance(raw, dict):
        return None
    for key in (_ENVELOPE_KEY,) + _LEGACY_ENVELOPE_KEYS:
        if raw.get(key):
            return raw.get("data", "")
    return None


def _dpapi_encrypt(text: str):
    """DPAPI-encrypt a string → base64 str, or None on failure."""
    try:
        import win32crypt
        blob = win32crypt.CryptProtectData(
            text.encode("utf-8"), "Stacka clipboard data", None, None, None, 0)
        return base64.b64encode(blob).decode("ascii")
    except Exception:
        return None


def _dpapi_decrypt(enc_b64: str):
    """DPAPI-decrypt a base64 blob → the original string, or None on failure."""
    try:
        import win32crypt
        blob = base64.b64decode(enc_b64.encode("ascii"))
        _desc, plain = win32crypt.CryptUnprotectData(blob, None, None, None, 0)
        return plain.decode("utf-8")
    except Exception:
        return None


def is_encryption_available() -> bool:
    """True when DPAPI can actually encrypt on this machine."""
    return _dpapi_encrypt("stacka") is not None


def read_json(path: str, default=None):
    """Load JSON from `path`, transparently handling BOTH the encrypted
    envelope and legacy plaintext. Returns `default` if unreadable."""
    try:
        with open(path, "r", encoding="utf-8") as f:
            raw = json.load(f)
    except Exception:
        return default

    # Encrypted envelope? (current stamp, or one written before the rename)
    blob = _envelope_blob(raw)
    if blob is not None:
        plain = _dpapi_decrypt(blob)
        if plain is None:
            # Wrong user / corrupt blob — do NOT silently return empty data,
            # let the caller fall back to its .bak like any other read failure.
            raise ValueError("could not decrypt (different Windows user?)")
        return json.loads(plain)

    # Legacy plaintext — fine; the next save re-writes it encrypted.
    return raw


def write_json(path: str, payload) -> bool:
    """Atomically write `payload` to `path`, ENCRYPTED when DPAPI is
    available (plaintext fallback otherwise). Keeps a .bak of the previous
    file. Returns True on success.

    Mirrors the original atomic strategy: write .tmp → fsync → back up the
    live file → os.replace(), so an interrupted write can never leave a
    half-written store behind.
    """
    global _warned
    tmp_path = path + ".tmp"
    bak_path = path + ".bak"
    try:
        os.makedirs(os.path.dirname(path), exist_ok=True)

        text = json.dumps(payload, indent=2, ensure_ascii=False)
        enc  = _dpapi_encrypt(text)
        if enc is not None:
            out = json.dumps({_ENVELOPE_KEY: 1, "data": enc})
        else:
            out = text          # fallback: never lose data over encryption
            if not _warned:
                print("[Stacka] DPAPI unavailable — storing data unencrypted.")
                _warned = True

        with open(tmp_path, "w", encoding="utf-8") as f:
            f.write(out)
            f.flush()
            os.fsync(f.fileno())

        if os.path.exists(path):
            try:
                import shutil
                shutil.copy2(path, bak_path)
            except Exception:
                pass            # backup failure is non-fatal

        os.replace(tmp_path, path)
        return True
    except Exception as e:
        print(f"[Stacka] Failed to write {os.path.basename(path)}: {e}")
        return False
