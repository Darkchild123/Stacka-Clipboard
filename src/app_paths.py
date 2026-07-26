# ============================================================
# Stacka - app_paths.py
# ============================================================
# One place that resolves file locations for BOTH the dev checkout
# and the packaged (PyInstaller) app.
#
#   resource_path(...) -> READ-ONLY bundled files (assets / icons).
#       frozen : PyInstaller's extraction dir  (sys._MEIPASS)
#       dev    : the project root
#
#   user_data_root()   -> WRITABLE per-user data (history, settings, images).
#       frozen : %APPDATA%\Stacka  (per-user, writable, survives updates,
#                and works even when the app is installed to Program Files)
#       dev    : the project root  (so the dev workflow is unchanged)
# ============================================================

import os
import sys

APP_NAME = "Stacka"

# In a dev checkout this file lives in src/, so the project root is one up.
_DEV_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


def is_frozen() -> bool:
    """True when running from a PyInstaller-built executable."""
    return getattr(sys, "frozen", False)


_packaged = None


def is_packaged() -> bool:
    """True when running inside an MSIX package (the Microsoft Store build).

    A packaged app has its registry writes VIRTUALIZED — they land in the
    package's private hive and never reach Explorer — so features that depend
    on registering with the shell simply cannot work there. Knowing which
    build we are lets the app skip those writes instead of performing them
    pointlessly, and lets Settings say so rather than leaving the user to
    wonder why an entry is missing.

    Detected with GetCurrentPackageFullName: it returns APPMODEL_ERROR_NO_PACKAGE
    (15700) when the process has no package identity.
    """
    global _packaged
    if _packaged is not None:
        return _packaged
    _packaged = False
    try:
        import ctypes
        APPMODEL_ERROR_NO_PACKAGE = 15700
        length = ctypes.c_uint32(0)
        rc = ctypes.windll.kernel32.GetCurrentPackageFullName(
            ctypes.byref(length), None)
        _packaged = (rc != APPMODEL_ERROR_NO_PACKAGE)
    except Exception:
        # Pre-Windows-8, or the call is unavailable — treat as unpackaged.
        _packaged = False
    return _packaged


def resource_dir() -> str:
    """Base folder for read-only bundled resources."""
    if is_frozen():
        # PyInstaller unpacks --add-data here (onefile AND onedir).
        return getattr(sys, "_MEIPASS", _DEV_ROOT)
    return _DEV_ROOT


def resource_path(*parts) -> str:
    """Absolute path to a bundled resource, e.g. resource_path('assets', 'icon.png')."""
    return os.path.join(resource_dir(), *parts)


def user_data_root() -> str:
    """Base folder for writable, per-user data."""
    if is_frozen():
        base = os.environ.get("APPDATA") or os.path.expanduser("~")
        return os.path.join(base, APP_NAME)
    return _DEV_ROOT
