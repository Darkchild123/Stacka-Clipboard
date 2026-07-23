# ============================================================
# ClipDrop - card_detect.py
# ============================================================
# Detects credit / debit card numbers in copied text and protects
# them: the real number is NEVER stored in the clear — it is
# encrypted at rest with Windows DPAPI (tied to the user account,
# no password needed) and only decrypted in memory to paste.
#
# Detection uses three local, offline checks (no AI, no network):
#   1. Regex   — the whole clipboard is 13-19 digits (spaces / dashes ok)
#   2. BIN     — the leading digits match a known card network + length
#   3. Luhn    — the mod-10 checksum every card network uses
# All three must pass, which makes false positives (order numbers,
# tracking numbers, IDs that merely have 16 digits) very unlikely.
#
# STEP 1 scope: only when the ENTIRE copied text is a single card
# number. Detecting a card embedded inside a larger paste comes later.
# ============================================================

import re

# Whole text = 13-19 digits, optionally single-spaced or dashed into groups.
_WHOLE_RE = re.compile(r"^\s*\d(?:[ -]?\d){12,18}\s*$")


def digits_only(text: str) -> str:
    """Strip everything but digits."""
    return re.sub(r"\D", "", text or "")


def luhn_ok(digits: str) -> bool:
    """The Luhn (mod-10) checksum used by every major card network:
    double every second digit from the right, subtract 9 if >9, sum all,
    and check it's a multiple of 10."""
    if not digits.isdigit() or len(digits) < 12:
        return False
    total = 0
    for i, ch in enumerate(reversed(digits)):
        d = int(ch)
        if i % 2 == 1:
            d *= 2
            if d > 9:
                d -= 9
        total += d
    return total % 10 == 0


def card_brand(digits: str):
    """Identify the card network from its BIN (leading digits) AND the
    length that network uses. Returns the brand name, or None if the
    prefix/length isn't a recognised card (this is what rejects random
    16-digit numbers that merely pass Luhn)."""
    if not digits.isdigit():
        return None
    n = len(digits)
    if not (12 <= n <= 19):
        return None
    d2 = int(digits[:2])
    d3 = int(digits[:3])
    d4 = int(digits[:4])

    if d2 in (34, 37) and n == 15:
        return "Amex"
    if digits[0] == "4" and n in (13, 16, 19):
        return "Visa"
    if (51 <= d2 <= 55 or 2221 <= d4 <= 2720) and n == 16:
        return "Mastercard"
    if (digits[:4] == "6011" or d2 == 65 or 644 <= d3 <= 649) and n in (16, 19):
        return "Discover"
    if (300 <= d3 <= 305 or d2 in (36, 38, 39)) and n == 14:
        return "Diners Club"
    if 3528 <= d4 <= 3589 and n in (16, 17, 18, 19):
        return "JCB"
    if d2 == 62 and n in (16, 17, 18, 19):
        return "UnionPay"
    return None


def detect_card(text: str):
    """Step 1: is the WHOLE copied text a single card number? Returns
    {'brand','last4','number'} when regex + BIN + Luhn all pass, else None."""
    if not isinstance(text, str) or not _WHOLE_RE.match(text):
        return None
    digits = digits_only(text)
    if not (13 <= len(digits) <= 19):
        return None
    brand = card_brand(digits)
    if brand is None or not luhn_ok(digits):
        return None
    return {"brand": brand, "last4": digits[-4:], "number": digits}


def mask(brand: str, last4: str) -> str:
    """The safe display form shown in the list — never the full number."""
    return f"{brand} •••• {last4}"


# ── Encryption at rest (Windows DPAPI) ──────────────────────────────────────

def encrypt(plaintext: str) -> str:
    """DPAPI-encrypt a string → base64 text for JSON storage. Returns "" on
    failure so the caller can decline to store the number in the clear."""
    try:
        import win32crypt
        import base64
        blob = win32crypt.CryptProtectData(
            plaintext.encode("utf-8"), "clipdrop-card", None, None, None, 0)
        return base64.b64encode(blob).decode("ascii")
    except Exception as e:
        print(f"[ClipDrop] Card encryption failed: {e}")
        return ""


def decrypt(enc_b64: str):
    """DPAPI-decrypt a base64 blob → the original string, or None on failure
    (e.g. the history was copied to a different Windows user or machine)."""
    try:
        import win32crypt
        import base64
        blob = base64.b64decode((enc_b64 or "").encode("ascii"))
        _desc, plain = win32crypt.CryptUnprotectData(blob, None, None, None, 0)
        return plain.decode("utf-8")
    except Exception as e:
        print(f"[ClipDrop] Card decryption failed: {e}")
        return None
