# ============================================================
# Stacka - clipboard_watcher.py
# ============================================================
# This file watches the Windows clipboard non-stop.
# Every time you copy something, it detects it, figures out
# what type it is (text, file, image), records where it came
# from, and sends it to the History Manager to be saved.
# ============================================================

import ctypes
import time
import re
import win32clipboard
import win32gui
import win32process
import psutil
from PIL import ImageGrab
import hashlib

# Matches text that is entirely a single URL (http, https, or bare www.)
_URL_RE = re.compile(r'^(https?://|www\.)[^\s]{4,}$', re.IGNORECASE)

# Matches a hex colour code: #RGB, #RGBA, #RRGGBB or #RRGGBBAA.
# The leading '#' is REQUIRED — without it ordinary words made entirely
# of hex letters ("decade", "cafe", "added") would false-positive.
_HEX_RE = re.compile(r'^#(?:[0-9a-fA-F]{3,4}|[0-9a-fA-F]{6}|[0-9a-fA-F]{8})$')


def _clipboard_seq():
    """Windows' clipboard sequence number, or None if it can't be read.

    It increments on EVERY copy — including re-copying identical content,
    which a content hash cannot distinguish from "nothing happened". That is
    the difference that makes re-copying a clip you deleted work.
    """
    try:
        return ctypes.windll.user32.GetClipboardSequenceNumber()
    except Exception:
        return None


class ClipboardWatcher:

    def __init__(self, history_manager):
        # history_manager is passed in from main.py
        # We store it here so we can send new items to it
        self.history = history_manager

        # We keep track of the last thing we saw in the clipboard
        # so we don't save the same item twice in a row
        self.last_seen = None

        # Clipboard sequence number of the last state we examined. This — not
        # the content hash — decides whether something new happened.
        self._last_seq = None

        # How often we check the clipboard (in seconds)
        # 0.5 = twice per second — fast enough to feel instant
        self.poll_interval = 0.5

        # Controls whether the watcher is running
        self.running = False

        # Pause flag — set to True while Stacka is pasting
        # so we don't accidentally record our own paste as a new copy
        self.paused = False


    def start(self):
        """
        Starts the clipboard watcher loop.
        This runs forever in the background until the app is closed.
        """
        self.running = True
        print("Clipboard watcher started.")

        while self.running:
            try:
                # Skip checking while Stacka is pasting
                if not self.paused:
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


    def mark_current_clipboard(self):
        """Treat whatever is on the clipboard RIGHT NOW as already seen.

        Called after the app writes the clipboard itself (a paste), so the
        watcher doesn't capture its own write as a fresh copy. Must run
        BEFORE un-pausing, or the next poll grabs it.
        """
        seq = _clipboard_seq()
        if seq is not None:
            self._last_seq = seq


    def check_clipboard(self):
        """
        Checks the clipboard for new content.
        If something new is found, it figures out what type it is
        and sends it to the history manager.
        """
        # Has the clipboard actually changed since we last looked? Re-copying
        # the SAME thing bumps this number, so a clip the user deleted can be
        # captured again by simply copying it a second time.
        seq = _clipboard_seq()
        if seq is not None and seq == self._last_seq:
            return

        try:
            win32clipboard.OpenClipboard()

            # --- Check for TEXT, URL, CODE, or BASH ---
            if win32clipboard.IsClipboardFormatAvailable(win32clipboard.CF_UNICODETEXT):
                content = win32clipboard.GetClipboardData(win32clipboard.CF_UNICODETEXT)
                content_type = self._classify_text(content)
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
                self._last_seq = seq     # examined — don't re-check this state
                return

            win32clipboard.CloseClipboard()

        except Exception:
            # Clipboard busy (another app holds it) — leave _last_seq alone so
            # this state is retried on the next poll.
            try:
                win32clipboard.CloseClipboard()
            except:
                pass
            return

        # This clipboard state has now been examined.
        self._last_seq = seq
        self.last_seen = content_id

        # Find out where it was copied from
        source = self.get_source()

        # If it's an image, grab it properly using PIL
        if content_type == "image":
            content = ImageGrab.grabclipboard()
            if content is None:
                return

        # --- Credit-card detection (whole clipboard is a card) ---
        # The real number is encrypted at rest (DPAPI) and never stored in the
        # clear. Only taken over if encryption succeeds — otherwise it falls
        # through and is saved as ordinary text rather than being lost.
        if content_type in ("text", "url", "code", "bash", "hex") and isinstance(content, str):
            import card_detect
            card = card_detect.detect_card(content)
            if card:
                enc = card_detect.encrypt(card["number"])
                if enc:
                    import uuid
                    self.history.add_item({
                        "id":      str(uuid.uuid4()),   # random — NEVER a hash of the number
                        "type":    "card",
                        "content": enc,                 # ciphertext, not the number
                        "brand":   card["brand"],
                        "last4":   card["last4"],
                        "source":  source,
                        "pinned":  False,
                    })
                    # No brand/last4 here: the log is plaintext on disk while
                    # the card itself is encrypted (see applog.py privacy note).
                    print("New item captured: [card]")
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
        # The source is the active window's title (a document name, a page
        # title, a URL…) — clipboard metadata, so it is deliberately NOT
        # written to the plaintext log. Type only.
        print(f"New item captured: [{content_type}]")


    def _classify_text(self, text):
        """
        Classifies copied text into one of five types:
          "url"  — entire text is a single URL
          "hex"  — a hex colour code (#FF5733, #0af, …)
          "bash" — shell/terminal commands
          "code" — programming code (any language)
          "text" — plain human-readable text (default)
        """
        stripped = text.strip()
        if not stripped:
            return "text"
        if _URL_RE.match(stripped):
            return "url"
        if _HEX_RE.match(stripped):
            return "hex"
        if self._is_bash(stripped):
            return "bash"
        if self._is_code(stripped):
            return "code"
        return "text"


    def _is_bash(self, text):
        """
        Returns True if the text looks like any shell or command-line input.
        Covers Unix/Linux bash, Windows CMD, and PowerShell.
        Uses a signal score — threshold of 3 prevents false positives.
        """
        import re
        signals = 0
        first_line = text.split('\n')[0].strip()
        first_word = first_line.split()[0].lower() if first_line.split() else ""

        # --- Instant returns (unambiguous single signals) ---

        # Shebang line
        if text.startswith(("#!/bin/bash", "#!/bin/sh",
                             "#!/usr/bin/env bash", "#!/usr/bin/env sh",
                             "#!/usr/bin/env python", "#!/usr/bin/env node")):
            return True

        # Multiple lines prefixed with $ (docs-style Unix blocks)
        dollar_lines = sum(1 for l in text.split('\n') if l.strip().startswith("$ "))
        if dollar_lines >= 2:
            return True

        # Multiple lines prefixed with a CMD prompt like C:\Users\>
        prompt_lines = sum(1 for l in text.split('\n')
                           if re.match(r'^\s*(>|[A-Z]:\\[^>]*>)\s+\S', l))
        if prompt_lines >= 2:
            return True

        # --- Command starters: two tiers ---
        #
        # STRONG_STARTERS  → +3 signals  (detected on their own, no extra signals needed)
        #   Words that are unambiguously command-line tools and never appear as
        #   the first word of a normal English sentence.
        #
        # WEAK_STARTERS    → +2 signals  (need one more signal to reach threshold 3)
        #   Words that could also start a natural-language sentence
        #   (e.g. "find the file", "move the box", "type your name").

        STRONG_STARTERS = {
            # Version control
            "git", "gh", "svn", "hg",
            # Package managers — these never start a sentence
            "sudo", "apt", "apt-get", "apt-cache", "yum", "dnf", "pacman",
            "brew", "pip", "pip3", "conda", "poetry",
            "npm", "npx", "yarn", "pnpm", "bun",
            # Container / cloud / infra
            "docker", "docker-compose", "podman", "kubectl", "helm",
            "terraform", "ansible", "vagrant",
            # Build / compile — cmake/mvn/gradle are unambiguous; make and go are
            # common English verbs so they live in WEAK_STARTERS instead.
            "cmake", "gcc", "g++", "clang", "mvn", "gradle",
            # Interpreters / runtimes  (people don't start sentences with these)
            "python", "python3", "ruby", "perl", "php", "cargo",
            "node", "deno", "java", "javac", "bun",
            # Remote / transfer
            "ssh", "scp", "sftp", "rsync", "curl", "wget",
            # Shells and shell utilities
            "bash", "sh", "zsh", "fish", "tmux", "screen",
            # System management
            "systemctl", "journalctl", "crontab", "launchctl",
            "pkill", "killall", "htop", "lsof", "strace",
            "nmap", "openssl", "dig", "nslookup",
            # Windows tools that are never plain English
            "ipconfig", "tracert", "pathping", "netsh", "robocopy", "xcopy",
            "wmic", "tasklist", "taskkill", "schtasks",
            "bcdedit", "diskpart", "sfc", "icacls", "takeown",
            "powercfg", "reg", "sc",
        }

        WEAK_STARTERS = {
            # Short Unix commands — common but could be acronyms/words.
            # "make" and "go" moved here from STRONG because they are ordinary
            # English verbs — they need a flag or pipe to confirm shell context.
            "make", "go",
            "cd", "ls", "ll", "la", "mkdir", "rm", "rmdir", "cp", "mv",
            "chmod", "chown", "chgrp", "ln", "touch", "cat", "less", "more",
            "head", "tail", "grep", "locate", "which", "whereis",
            "awk", "sed", "cut", "tr", "uniq", "wc", "diff", "patch",
            "tar", "zip", "unzip", "gzip", "gunzip",
            "echo", "printf", "export", "source", "env", "printenv",
            "kill", "ps", "top", "df", "du", "mount", "umount",
            "fdisk", "lsblk", "ifconfig", "ip", "ping", "traceroute",
            "ss", "netstat", "xargs", "tee", "watch", "vim", "nano",
            "uname", "hostname", "whoami", "uptime", "free",
            # Windows CMD words that could also be English
            "dir", "cls", "type", "del", "erase", "copy",
            "move", "ren", "rename", "md", "rd", "attrib",
            "net", "route", "arp", "runas", "start", "chkdsk",
            "assoc", "ftype", "color", "title", "mode",
            "findstr", "fc", "compact", "cipher", "fsutil",
        }

        if first_word in STRONG_STARTERS:
            # These tool names never appear as the first word of a normal English
            # sentence — treat as bash immediately without waiting for more signals.
            return True
        elif first_word in WEAK_STARTERS:
            signals += 2    # Needs one more signal to avoid false positives

        # Command with Unix-style flags  (e.g. "ls -la" / "curl -X POST -H")
        if re.match(r'^[a-z][\w.-]*(\s+(-{1,2}[\w-]+))+', first_line, re.IGNORECASE):
            signals += 2

        # Command with Windows-style switches  (e.g. "dir /w /b" / "netstat /an")
        if re.match(r'^[a-z][\w.-]*(\s+(\/[\w]+))+', first_line, re.IGNORECASE):
            signals += 2

        # Single $ prompt line
        if first_line.startswith("$ "):
            signals += 2

        # Windows CMD prompt in first line  (e.g.  C:\Users\Cosmas> dir /w)
        if re.match(r'^[A-Z]:\\[^>]*>\s+\S', first_line):
            signals += 3

        # Running a local script:  .\script.ps1  or  ./run.sh
        if re.search(r'^\s*[.\\][\\\/]\w', text, re.MULTILINE):
            signals += 2

        # --- Shell-specific syntax ---
        if "| grep" in text or "| awk" in text or "| sed" in text:
            signals += 2
        if ">>" in text or "2>&1" in text or "/dev/null" in text:
            signals += 1
        if "$(" in text:
            signals += 1    # Command substitution $(...)

        # Windows CMD: %VARIABLE% environment variable references
        if re.search(r'%[A-Z_][A-Z0-9_]*%', text, re.IGNORECASE):
            signals += 2
        # CMD batch keywords
        if re.search(r'^@?echo\b|^goto\b|^call\b', text,
                     re.IGNORECASE | re.MULTILINE):
            signals += 2
        if re.search(r'\bif\s+(exist|errorlevel|defined)\b', text, re.IGNORECASE):
            signals += 2
        if re.search(r'\bfor\s+/[fFdDlLrR]\b', text, re.IGNORECASE):
            signals += 2

        # --- PowerShell detection ---
        # Verb-Noun cmdlet pattern (Get-Item, Set-Variable, Install-Module etc.)
        # Requires an UPPERCASE letter after the hyphen — real PowerShell cmdlets
        # always follow the Verb-Noun (both capitalised) convention, so this avoids
        # false positives on common English hyphenated words like "Set-up", "Write-up",
        # "Start-up", "Copy-paste", "Move-in", "Read-only", "Select-all", "Add-on".
        ps_cmdlet = re.search(
            r'\b(Get|Set|New|Remove|Install|Uninstall|Import|Export|'
            r'Invoke|Start|Stop|Restart|Enable|Disable|Add|Clear|'
            r'Copy|Move|Rename|Test|Out|Select|Where|ForEach|'
            r'Write|Read|Push|Pop|Register|Unregister)-[A-Z]\w+',
            text
        )
        if ps_cmdlet:
            signals += 2
        # $Variable assignments or references — only count when used in a way
        # that looks like real PowerShell code (assignment, method/property call,
        # or pipeline use). This prevents plain text mentioning $total, $amount,
        # $name etc. from racking up false signals.
        ps_vars = len(re.findall(
            r'\$[A-Za-z_]\w*\s*(?:[=.(|,])',  # $var = / $var. / $var( / $var| / $var,
            text
        ))
        if ps_vars >= 2:
            signals += 2
        # PowerShell pipe with cmdlets
        if re.search(r'\|\s*(Select|Where|ForEach|Sort|Group|'
                     r'Format|Out|Measure)-', text):
            signals += 2
        # PowerShell type annotations [string], [int], [Parameter(
        if re.search(r'\[(string|int|bool|array|Parameter|CmdletBinding)\b', text):
            signals += 1

        # Threshold raised to 4 (was 3) because STRONG_STARTERS now short-circuit
        # with an early return True, so the scoring path is only reached by
        # WEAK_STARTERS and contextual signals. A higher bar prevents the case
        # where a WEAK word + one tiny coincidental signal (>>  or  $() alone)
        # tips ordinary text over into a false bash classification.
        return signals >= 4


    def _is_code(self, text):
        """
        Returns True if the text looks like programming code.
        Uses a weighted pattern score — threshold of 5 prevents
        false positives on regular sentences that happen to contain
        words like 'return' or 'class'.
        """
        import re
        score = 0
        lines = text.split('\n')

        PATTERNS = [
            (r'\bdef\s+\w+\s*\(',            3),   # Python function def
            (r'\bclass\s+\w+[\s:(]',         2),   # Class definition
            (r'^(from|import)\s+\w+',        2),   # Python/JS import
            (r'\bfunction\s*\w*\s*\(',       3),   # JS function
            (r'\b(const|let|var)\s+\w+\s*=', 2),  # JS/TS variable
            (r'=>\s*[{(]',                   2),   # Arrow function
            (r'#include\s*[<"]',             4),   # C/C++
            (r'\bpublic\s+(class|void|static|int)', 4),  # Java
            (r'^\s*<\?php',                  4),   # PHP
            (r'^\s*fn\s+\w+\s*\(',           4),   # Rust
            (r'\breturn\s+.+[;\n]',          1),   # return statement
            (r'^\s*(//|/\*|\*)',             1),   # // or /* comments
            (r'^\s*#\s+\w',                  1),   # # comment (Python/bash — low weight)
            (r';\s*$',                       1),   # Lines ending with semicolon
            (r'\{[\s\S]*?\}',               1),   # Curly brace blocks
            (r'\bif\s*\(.+\)',              1),   # if () condition
            (r'\bfor\s*\(',                 1),   # for loop
            (r'==|!=|<=|>=|&&|\|\|',        1),   # Comparison/logical operators
        ]

        for pattern, weight in PATTERNS:
            if re.search(pattern, text, re.MULTILINE):
                score += weight

        # Bonus for multi-line text — real code tends to have several lines
        if len(lines) >= 4:
            score += 1
        # Bonus for consistent indentation (spaces at line starts)
        indented = sum(1 for l in lines if l.startswith(("    ", "\t")))
        if indented >= 2:
            score += 2

        return score >= 5


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
