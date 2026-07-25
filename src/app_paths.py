# ============================================================
# ClipDrop - app_paths.py
# ============================================================
# One place that resolves file locations for BOTH the dev checkout
# and the packaged (PyInstaller) app.
#
#   resource_path(...) -> READ-ONLY bundled files (assets / icons).
#       frozen : PyInstaller's extraction dir  (sys._MEIPASS)
#       dev    : the project root
#
#   user_data_root()   -> WRITABLE per-user data (history, settings, images).
#       frozen : %APPDATA%\ClipDrop  (per-user, writable, survives updates,
#                and works even when the app is installed to Program Files)
#       dev    : the project root  (so the dev workflow is unchanged)
# ============================================================

import os
import sys

APP_NAME = "ClipDrop"

# In a dev checkout this file lives in src/, so the project root is one up.
_DEV_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


def is_frozen() -> bool:
    """True when running from a PyInstaller-built executable."""
    return getattr(sys, "frozen", False)


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
