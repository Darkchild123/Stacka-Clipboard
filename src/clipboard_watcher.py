# ============================================================
# ClipDrop - clipboard_watcher.py
# ============================================================
# This file watches the Windows clipboard non-stop.
# Every time you copy something, it detects it, figures out
# what type it is (text, file, image), records where it came
# from, and sends it to the History Manager to be saved.
# ============================================================

import time
import win32clipboard
import win32gui
import win32process
import psutil
from PIL import ImageGrab
import hashlib


class ClipboardWatcher:

    def __init__(self, history_manager):
        # history_manager is passed in from main.py
        # We store it here so we can send new items to it
        self.history = history_manager

        # We keep track of the last thing we saw in the clipboard
        # so we don't save the same item twice in a row
        self.last_seen = None

        # How often we check the clipboard (in seconds)
        # 0.5 = twice per second — fast enough to feel instant
        self.poll_interval = 0.5

        # Controls whether the watcher is running
        self.running = False


    def start(self):
        """
        Starts the clipboard watcher loop.
        This runs forever in the background until the app is closed.
        """
        self.running = True
        print("Clipboard watcher started.")

        while self.running:
            try:
                self.check_clipboard()
            except Exception as e:
                # If something goes wrong, we log it but keep running
                print(f"Watcher error: {e}")

            # Wait before checking again
            time.sleep(self.poll_interval)


    def stop(self):
        """Stops the clipboard watcher."""
        self.running = False
        print("Clipboard watcher stopped.")


    def check_clipboard(self):
        """
        Checks the clipboard for new content.
        If something new is found, it figures out what type it is
        and sends it to the history manager.
        """
        try:
            win32clipboard.OpenClipboard()

            # --- Check for TEXT ---
            if win32clipboard.IsClipboardFormatAvailable(win32clipboard.CF_UNICODETEXT):
                content = win32clipboard.GetClipboardData(win32clipboard.CF_UNICODETEXT)
                content_type = "text"
                content_id = self._hash(content)

            # --- Check for FILES ---
            elif win32clipboard.IsClipboardFormatAvailable(win32clipboard.CF_HDROP):
                files = win32clipboard.GetClipboardData(win32clipboard.CF_HDROP)
                content = list(files)  # Convert to a list of file paths
                content_type = "file"
                content_id = self._hash(str(content))

            # --- Check for IMAGES ---
            elif win32clipboard.IsClipboardFormatAvailable(win32clipboard.CF_DIB):
                content_type = "image"
                content_id = self._get_image_hash()
                content = "image"  # Actual image is grabbed below

            else:
                # Nothing we recognise in the clipboard
                win32clipboard.CloseClipboard()
                return

            win32clipboard.CloseClipboard()

        except Exception:
            try:
                win32clipboard.CloseClipboard()
            except:
                pass
            return

        # If it's the same as the last thing we saw, skip it
        if content_id == self.last_seen:
            return

        # It's new! Update what we last saw
        self.last_seen = content_id

        # Find out where it was copied from
        source = self.get_source()

        # If it's an image, grab it properly using PIL
        if content_type == "image":
            content = ImageGrab.grabclipboard()
            if content is None:
                return

        # Build a clipboard item as a dictionary
        # Think of a dictionary like a labelled container with named slots
        item = {
            "id": content_id,           # Unique identifier for this item
            "type": content_type,       # "text", "file", or "image"
            "content": content,         # The actual copied content
            "source": source,           # Where it was copied from
            "pinned": False,            # Not pinned by default
        }

        # Send the item to the History Manager to be saved
        self.history.add_item(item)
        print(f"New item captured: [{content_type}] from {source}")


    def get_source(self):
        """
        Figures out where the copied content came from.
        It checks what window was active when you copied something
        and returns a human-readable source label.
        """
        try:
            # Get the currently active window
            hwnd = win32gui.GetForegroundWindow()

            # Get the process ID of that window
            _, pid = win32process.GetWindowThreadProcessId(hwnd)

            # Get the process name (e.g. "chrome.exe", "notepad.exe")
            process = psutil.Process(pid)
            process_name = process.name()

            # Get the window title (e.g. "Report.docx - Word")
            window_title = win32gui.GetWindowText(hwnd)

            # Try to extract a URL if the active window is a browser
            source = self._extract_source(process_name, window_title)
            return source

        except Exception:
            return "Unknown"


    def _extract_source(self, process_name, window_title):
        """
        Turns the process name and window title into a clean source label.
        For example:
          - chrome.exe + "Google - Chrome" → "Google (Chrome)"
          - WINWORD.EXE + "report.docx"   → "report.docx (Word)"
          - explorer.exe                  → "File Explorer"
        """
        name = process_name.lower()

        if "chrome" in name:
            return f"{window_title.replace(' - Google Chrome', '').strip()} (Chrome)"
        elif "firefox" in name:
            return f"{window_title.replace(' — Mozilla Firefox', '').strip()} (Firefox)"
        elif "msedge" in name:
            return f"{window_title.replace(' - Microsoft Edge', '').strip()} (Edge)"
        elif "notepad" in name:
            return f"{window_title} (Notepad)"
        elif "winword" in name:
            return f"{window_title.replace(' - Word', '').strip()} (Word)"
        elif "excel" in name:
            return f"{window_title.replace(' - Excel', '').strip()} (Excel)"
        elif "explorer" in name:
            return "File Explorer"
        elif "code" in name:
            return f"{window_title.replace(' - Visual Studio Code', '').strip()} (VS Code)"
        else:
            # For anything else, just return the window title
            return window_title if window_title else process_name


    def _hash(self, text):
        """
        Creates a unique fingerprint for a piece of text.
        We use this to detect if the same thing was copied twice.
        """
        return hashlib.md5(text.encode("utf-8", errors="ignore")).hexdigest()


    def _get_image_hash(self):
        """
        Creates a unique fingerprint for an image in the clipboard.
        """
        try:
            img = ImageGrab.grabclipboard()
            if img:
                import io
                buffer = io.BytesIO()
                img.save(buffer, format="PNG")
                return hashlib.md5(buffer.getvalue()).hexdigest()
        except:
            pass
        return str(time.time())  # Fallback: use timestamp as unique ID
