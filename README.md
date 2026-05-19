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

**Status:** 🔧 Fix in progress

**What happens:**
The dropdown popup appears correctly the first time it is triggered. On the second trigger, a Python window flashes on screen briefly and disappears repeatedly without showing the popup.

**Root cause:**
`tkinter` (the UI library used for the popup) only allows one main window (`Tk()`) to exist at a time. Every time the popup is triggered, the code tries to create a brand new main window — causing a conflict that results in the flickering behaviour.

**Planned fix:**
Restructure `dropdown_popup.py` to reuse a single persistent window instead of creating a new one each time it is triggered.

**File affected:** `src/dropdown_popup.py`

---

### 🐛 Bug 2 — "Paste from ClipDrop" Only Appears on the Desktop

**Status:** 🔧 Fix in progress

**What happens:**
The "Paste from ClipDrop" option appears correctly when right-clicking on the Desktop or inside File Explorer. It does not appear when right-clicking inside applications such as Notepad, browsers, or HTML forms.

**Root cause:**
Windows has two separate types of right-click menus. The Windows Registry approach (used in v1.0) only covers the Windows Shell — the Desktop and File Explorer. Applications like Notepad, Chrome, and Word build their own right-click menus independently and do not allow external injection via the Registry.

**Planned fix:**
Implement a low-level system-wide mouse hook that intercepts right-click events at the Windows level — before any application handles them. This will display a custom ClipDrop menu overlay across all applications. The existing `Ctrl+Shift+V` hotkey will also be promoted as a primary trigger that works everywhere without needing a right-click.

**File affected:** `src/context_menu.py`

---

| Date | Milestone |
|---|---|
| 2026-05-07 | Project concept defined, design document completed |
| 2026-05-07 | Project folder and GitHub repository initialized |
| 2026-05-15 | All 7 source files written — core engine, UI, and Windows integration |
| 2026-05-15 | First live test — app launches, tray icon works, clipboard monitoring works |
| 2026-05-15 | First live test — popup shows on first trigger, 2 bugs identified and documented |

---

## About This Project

ClipDrop is being built by **Cosmas** as a first software development project — going from idea to working application. The goal is to learn by building something genuinely useful.

---

*Built with passion. Designed for simplicity.*
