# ClipDrop 📋

> A lightweight Windows clipboard manager that lets you copy multiple items, organize them your way, and choose exactly what to paste — right where your cursor is.

---

## 📌 Table of Contents

- [Overview](#overview)
- [The Problem](#the-problem)
- [The Solution](#the-solution)
- [Features](#features)
- [How It Works](#how-it-works)
- [App Structure](#app-structure)
- [Data Storage](#data-storage)
- [Design Decisions](#design-decisions)
- [Roadmap](#roadmap)
- [Known Issues](#known-issues)
- [Development Log](#development-log)

---

## Overview

**ClipDrop** is a Windows clipboard manager built for everyday users who copy and paste frequently. It runs silently in the background, saves everything you copy, and gives you a clean dropdown list — right at your cursor — so you can choose exactly what to paste.

Built from scratch as a personal software development project by a first-time developer with a great idea.

---

## The Problem

Windows (and most operating systems) only remember **one copied item at a time**. The moment you copy something new, the previous item is gone forever. This is frustrating when:

- You're copying multiple pieces of text from different sources
- You accidentally overwrite something important you copied earlier
- You need to paste the same few things repeatedly across different places

---

## The Solution

ClipDrop solves this by:

1. **Silently monitoring** everything you copy in the background
2. **Saving a history** of copied items (text, files, and images)
3. **Injecting a "Paste from ClipDrop"** option into the Windows right-click context menu
4. **Displaying a popup dropdown** right at your cursor position when triggered
5. Letting you **click any item** to paste it instantly

---

## Features

| Feature | Description |
|---|---|
| 📋 Clipboard Monitoring | Automatically captures text, files, and images as you copy |
| 🖱️ Right-Click Integration | Adds "Paste from ClipDrop" to the Windows context menu |
| 📍 Cursor-Position Dropdown | Popup list appears exactly where your mouse cursor is |
| 👁️ Item Previews | First few words for text, icon for files, thumbnail for images |
| 🔁 Smart Deduplication | Copying the same item again moves it to the top — no duplicates |
| 💾 Persistent History | History is saved to disk and survives restarts |
| 📌 Pin Items | Pin important items so they stay at the top and are never auto-removed |
| 🗑️ Delete Items | Remove any individual item from your history |
| 🔢 User-Defined History Size | You choose how many items to keep in Settings |
| ⚙️ System Tray Icon | App runs in background; access Settings or Quit from the tray |
| 🧹 Clear All History | One-click clear from Settings or tray menu |
| ↕️ Reorder Items | Manually move items up or down the list to suit your workflow |
| 🔍 Source Tracking | Each item shows where it was copied from — file path, directory, or URL |

---

## How It Works

### User Flow

```
User copies something (text / file / image)
        ↓
ClipDrop silently saves it to history
        ↓
User right-clicks anywhere (e.g. in a text editor, browser, file explorer)
        ↓
"Paste from ClipDrop" appears in the context menu
        ↓
User clicks it → dropdown popup appears at cursor position
        ↓
List shows all saved items with previews
        ↓
User clicks desired item → it gets pasted instantly
```

### Item Previews

| Item Type | Preview Shown |
|---|---|
| Text | First few words of the copied text |
| File | File type icon + file name |
| Image | Small thumbnail of the image |

### Source Tracking

Each item in the dropdown displays where it was originally copied from:

| Source Type | Example |
|---|---|
| File / Directory | `C:\Documents\report.docx` |
| Web URL | `https://example.com/article` |
| Application | `Microsoft Word`, `Notepad`, etc. |

### Reordering Items

Items in the dropdown can be manually rearranged — move any item up or down the list to match your workflow. Pinned items always stay at the top regardless of order.

---

## App Structure

```
ClipDrop/
│
├── src/                        # All source code
│   ├── main.py                 # App entry point
│   ├── clipboard_watcher.py    # Monitors clipboard for new copies
│   ├── history_manager.py      # Saves, loads, deduplicates, pins history
│   ├── context_menu.py         # Injects into Windows right-click menu
│   ├── dropdown_popup.py       # The cursor-position dropdown UI
│   ├── tray_icon.py            # System tray icon and menu
│   └── settings_panel.py       # Simple settings window
│
├── assets/                     # Icons, thumbnails, UI assets
│
├── data/                       # Persistent clipboard history (saved locally)
│
├── settings/                   # User preferences (history size, etc.)
│
└── README.md                   # This file
```

### Component Breakdown

**Background Service**
- `clipboard_watcher.py` — detects every new copy event
- `history_manager.py` — manages saving, deduplication, pinning, and persistence

**UI Components**
- `dropdown_popup.py` — the popup list that appears at the cursor
- `tray_icon.py` — system tray icon with quick actions
- `settings_panel.py` — simple settings window

**Windows Integration**
- `context_menu.py` — hooks into the Windows right-click context menu

---

## Data Storage

- All history is stored **locally on the user's PC** — no cloud, no internet required
- History is saved as a structured file in the `data/` folder
- Images are stored as **small thumbnails** to keep file size low
- Pinned items are flagged separately so they are never auto-removed
- Settings (like history size) are stored in the `settings/` folder

---

## Design Decisions

| Decision | Choice | Reason |
|---|---|---|
| Trigger method | Right-click context menu | Most natural and familiar for Windows users |
| History size | User-defined | Flexibility — different users have different needs |
| Duplicates | Move to top | Cleaner list, most recent copy is always accessible |
| Persistence | Saved to disk | Protects against accidental restarts or shutdowns |
| Storage | Local only | Privacy-first — your clipboard data stays on your machine |
| Scope (v1) | Text, files, images | Covers all common copy-paste use cases |

---

## Roadmap

### Version 1.0 (MVP)
- [x] App design and concept defined
- [ ] Clipboard monitoring (text, files, images)
- [ ] Persistent history storage
- [ ] Right-click context menu integration
- [ ] Cursor-position dropdown popup
- [ ] Item previews (text snippet, file icon, image thumbnail)
- [ ] Pin and delete per item
- [ ] Reorder items (move up / move down)
- [ ] Source tracking (file path, directory, or URL per item)
- [ ] System tray icon
- [ ] Simple settings panel (history size, clear history)
- [ ] Installer / packaged .exe for Windows

### Future Ideas (v2+)
- [ ] Search through clipboard history
- [ ] Keyboard shortcut to open ClipDrop
- [ ] Favourites / named clips
- [ ] Auto-clear history after X days
- [ ] Dark mode / theme options

---

## Known Issues

These bugs were discovered during the first live test of ClipDrop v1.0 and are actively being worked on:

---

### 🐛 Bug 1 — Popup Flickers and Vanishes on Second Trigger

**Status:** ✅ Resolved

**What happened:**
The dropdown popup appeared correctly the first time it was triggered. On the second trigger, a Python window flashed on screen briefly and disappeared repeatedly without showing the popup.

**Root cause:**
`tkinter` (the UI library used for the popup) only allows one main window (`Tk()`) to exist at a time. Every time the popup was triggered, the code tried to create a brand new main window — causing a conflict that resulted in the flickering behaviour.

**How it was fixed:**
The popup was restructured to use `Toplevel` — a child window of a single shared `Tk()` root — instead of creating a new `Tk()` instance every time. The root window is created once at startup in `main.py` and shared across the entire app. The popup simply shows and hides this child window on demand using `deiconify()` and `withdraw()`, eliminating the conflict entirely.

**Files changed:** `src/main.py`, `src/dropdown_popup.py`

---

### 🐛 Bug 2 — Tray Icon Not Running

**Status:** ✅ Resolved

**What happened:**
After the popup fix, the system tray icon stopped appearing. ClipDrop launched but showed no tray icon, making it impossible to access settings or quit the app cleanly.

**Root cause:**
`tkinter` and `pystray` (the tray icon library) both require ownership of the main thread to run their event loops. They were fighting each other — whichever started second would fail silently.

**How it was fixed:**
The app architecture was restructured so that `tkinter` exclusively owns the main thread via `root.mainloop()`. All other components — `pystray`, the clipboard watcher, and the context menu — were moved to background daemon threads. A shared `root` object is passed between components, and `root.after()` is used as a safe messenger to trigger UI updates from background threads onto the main thread.

**Files changed:** `src/main.py`, `src/tray_icon.py`, `src/context_menu.py`, `src/dropdown_popup.py`

---

### 🐛 Bug 3 — File Paste Not Working

**Status:** ✅ Resolved

**What happened:**
Copying a file and selecting it from the ClipDrop popup did nothing — the file was not pasted into the destination.

**Root cause — wrong binary structure:**
Windows requires file clipboard data (`CF_HDROP`) in a precise binary format called a `DROPFILES` structure — a 20-byte header followed by Unicode file paths each separated by null characters. The original code packed the header as 24 bytes (6 integers) instead of the correct 20 bytes (5 integers), causing Windows to silently reject the data.

**Root cause — clipboard loop:**
When ClipDrop restored the file path to the clipboard before pasting, the clipboard watcher detected this as a new copy event and tried to save it as a new history item — interfering with the paste operation.

**How it was fixed:**
The `DROPFILES` header was corrected to exactly 20 bytes using `struct.pack("<5I", 20, 0, 0, 0, 1)`. A `paused` flag was added to the clipboard watcher — the watcher skips checking while ClipDrop is performing a paste, then automatically resumes after 0.5 seconds, preventing the loop.

**Files changed:** `src/dropdown_popup.py`, `src/clipboard_watcher.py`

---

### 🐛 Bug 4 — "Paste from ClipDrop" Only Appears on the Desktop

**Status:** ✅ Resolved

**What happened:**
The "Paste from ClipDrop" option appeared correctly when right-clicking on the Desktop or inside File Explorer. It did not appear when right-clicking inside applications such as Notepad, browsers, or HTML forms.

**Root cause:**
Windows has two separate types of right-click menus. The Windows Registry approach only covers the Windows Shell — the Desktop and File Explorer. Applications like Notepad, Chrome, and Word build their own right-click menus independently and do not allow external injection via the Registry.

**How it was fixed:**
A low-level Windows mouse hook (`WH_MOUSE_LL`) was implemented using the Windows API via Python's `ctypes` library. This hook detects every right-click system-wide — in any application, browser, text editor, or HTML form. When a right-click is detected, a small floating **"📋 Paste from ClipDrop"** button appears near the cursor. The native right-click menu still opens as normal. Clicking the button opens the ClipDrop popup. The button auto-disappears after 3 seconds if not clicked. The `Ctrl+Shift+V` hotkey remains available as a keyboard alternative.

**Files changed:** `src/context_menu.py`

---

### 🐛 Bug 5 — App Quits on Its Own / Mouse Freezes

**Status:** ✅ Resolved

**What happened:**
Two symptoms appeared together: the app would quit unexpectedly with the tray icon disappearing, and the mouse would freeze completely requiring Ctrl+Alt+Del to recover.

**Root cause:**
The low-level mouse hook callback (`hook_proc`) was crashing with an `OverflowError` on every single mouse event. On 64-bit Windows, the `lParam` pointer passed to `CallNextHookEx` is a 64-bit integer. Without explicit type declarations, `ctypes` defaulted to treating it as 32-bit, causing it to overflow. The crash happened silently on every mouse movement, flooding the console with errors, jamming the mouse event queue, and eventually killing background threads which caused the app to appear to quit.

**How it was fixed:**
Explicit `argtypes` and `restype` were declared for every Windows API call involved in the hook — `SetWindowsHookExW`, `CallNextHookEx`, `UnhookWindowsHookEx`, and `GetMessageW`. Declaring `wintypes.LPARAM` for the `lParam` argument tells `ctypes` to handle it as a pointer-sized 64-bit value, eliminating the overflow. Additionally, a `protected_thread()` wrapper was added in `main.py` — every background component now runs inside a `try/except` so a crash in one thread never takes down the whole app.

**Files changed:** `src/context_menu.py`, `src/main.py`

---

| Date | Milestone |
|---|---|
| 2026-05-07 | Project concept defined, design document completed |
| 2026-05-07 | Project folder and GitHub repository initialized |
| 2026-05-15 | All 7 source files written — core engine, UI, and Windows integration |
| 2026-05-15 | First live test — app launches, tray icon works, clipboard monitoring confirmed |
| 2026-05-15 | 3 bugs identified and documented during first live test |
| 2026-05-20 | Bug 1 fixed — popup flicker resolved by switching to Toplevel window pattern |
| 2026-05-20 | Bug 2 fixed — tray icon restored by restructuring threading architecture |
| 2026-05-20 | Bug 3 fixed — file paste corrected with proper CF_HDROP binary format and clipboard loop prevention |
| 2026-05-20 | App confirmed stable — text and file copy/paste working correctly |
| 2026-05-24 | Bug 4 fixed — right-click overlay now works in all apps via low-level mouse hook |
| 2026-05-24 | Bug 5 fixed — ctypes 64-bit overflow resolved, crash protection added to all threads |
| 2026-05-24 | App confirmed working — right-click overlay, hotkey, tray icon all stable |

---

## About This Project

ClipDrop is being built by **Cosmas** as a first software development project — going from idea to working application with the help of AI-assisted development tools. The goal is to learn by building something genuinely useful.

---

*Built with passion. Designed for simplicity.*
