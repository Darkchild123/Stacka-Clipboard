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
| 🖐️ Draggable Popup | Drag the ClipDrop popup by its header to reposition it anywhere on screen |

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
│   ├── clipboard_watcher.py    # Monitors clipboard, classifies copied content
│   ├── history_manager.py      # Saves, loads, deduplicates, pins history
│   ├── profile_manager.py      # Named clipboard collections (profiles)
│   ├── context_menu.py         # Right-click integration, triggers, hotkeys
│   ├── dropdown_popup.py       # The cursor-position dropdown UI + icon engine
│   ├── icon_packs.py           # Optional per-extension "Labeled" icon pack
│   ├── snippet_window.py       # Blank scratchpad for new snippets
│   ├── tray_icon.py            # System tray icon and menu
│   └── settings_panel.py       # Settings window + Shortcuts manager
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
- [x] Clipboard monitoring (text, files, images)
- [x] Persistent history storage
- [x] Right-click context menu integration
- [x] Cursor-position dropdown popup
- [x] Item previews (text snippet, file icon, image thumbnail)
- [x] Pin and delete per item
- [x] Reorder items (move up / move down)
- [x] Source tracking (file path, directory, or URL per item)
- [x] System tray icon
- [x] Settings panel (history size, themes, transparency, close behaviour, profiles)
- [ ] Installer / packaged .exe for Windows
- [ ] Code-sign the executable (avoids AV false-positives from the mouse hook)

### Delivered beyond MVP
- [x] Search through clipboard history (live filtering)
- [x] Fully configurable global shortcuts with a dedicated manager window
- [x] Profiles — named clipboard collections with per-profile pins
- [x] Dark / light themes with live switching
- [x] Multi-file side panel with per-file actions and nested folder preview
- [x] Hex colour code detection with live colour swatch icons
- [x] Content counts on multi-file and folder rows
- [x] In-app toast notifications for every action
- [x] Ctrl+click multi-selection with combined paste (all lists)
- [x] Drag & drop items out of ClipDrop into any app
- [x] Snippet scratchpad — type a note, save it straight into history
- [x] Pause/resume capture, clear history, and profile cycling by hotkey
- [x] Six selectable trigger modes (mouse gestures, hotkey, or overlay button)
- [x] SVG icon system with selectable icon packs and per-extension detection
- [x] Adjustable UI sizing (window, rows, side list) in 10% steps
- [x] Open files / folders / links straight from the list (right-click)

### Future Ideas (v2+)
- [ ] Auto-clear history after X days
- [ ] Windows Store packaging

---

## Known Limitations

These are inherent to how Windows secures and renders the desktop — not
bugs, but constraints ClipDrop works within.

### Apps running as Administrator

Windows' User Interface Privilege Isolation (UIPI) forbids a normal-
privilege process from inspecting, hooking, or drawing over a window
owned by a **higher-privilege** process. So when ClipDrop runs normally
(the recommended way), its "Paste from ClipDrop" overlay button will
**not appear** over apps launched as Administrator — an elevated
Terminal, Task Manager, or an IDE run as admin. The clipboard itself
still works everywhere; only the right-click overlay is blocked for
those windows. Running ClipDrop itself as Administrator lifts the
restriction, at the cost of the app starting elevated.

### In-page (web / Electron) context menus

Apps that draw their right-click menus inside their own window as
HTML — the Claude app, Slack, Teams, some web apps — expose no window
handle to measure. ClipDrop falls back to **UI Automation** (the
accessibility layer) to read those menus' bounds. This works for most
Chromium/Electron apps, but their accessibility tree wakes *lazily*, so
the very first right-click in a freshly launched app may miss (the
button positions by cursor heuristic); subsequent clicks land correctly.
Apps that expose nothing to accessibility keep the cursor-side fallback.

### Distribution note — code signing

ClipDrop uses a low-level mouse hook (`SetWindowsHookEx`) for its
system-wide right-click detection. This is legitimate, but unsigned
executables using such hooks can trip antivirus heuristics. Before the
Microsoft Store release the packaged `.exe` must be **digitally signed**
(the Store submission process handles this) so Defender and third-party
AV recognise it as trusted.

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

### 🐛 Bug 6 — Overlay Button Closes Native Context Menu

**Status:** ✅ Resolved

**What happened:**
When the floating "📋 Paste from ClipDrop" button appeared after a right-click, the native context menu would immediately flash and disappear, leaving only the ClipDrop button on screen.

**Root cause:**
`focus_force()` was being called on the overlay window after it appeared. Windows closes a context menu the instant it loses focus. Calling `focus_force()` on our overlay stole focus away from the context menu, causing Windows to close it immediately.

**How it was fixed:**
Removed `focus_force()` from the overlay display logic entirely. The overlay button is fully clickable without having focus — it just needs to be visible. The `<FocusOut>` binding on the overlay was also removed since it served no purpose once the overlay no longer takes focus.

**Files changed:** `src/context_menu.py`

---

### 🐛 Bug 7 — Overlay Button Overlapping the Context Menu

**Status:** ✅ Resolved

**What happened:**
The floating "📋 Paste from ClipDrop" button was appearing on top of the native context menu in many apps, making both hard to use.

**Root cause — timing:**
The context menu window search ran immediately on the main thread. Many apps take longer than 120ms to render their context menu, so the search returned nothing and the fallback placed the button near the cursor — right where the menu had just appeared.

**Root cause — clamping overlap:**
When the context menu sat near the bottom of the screen, the "below" placement was calculated correctly but screen-edge clamping pulled the button back up into the menu. The code committed to a direction before verifying the clamped position was actually clear.

**Root cause — fallback positioning:**
When the menu window could not be found at all (many apps and HTML forms do not use the standard Windows `#32768` menu class), the fallback guessed a position near the cursor without knowing where the menu was, often landing directly on it.

**How it was fixed:**
Three separate fixes were applied. First, the context menu search was moved to a background thread with retry logic — polling up to 300ms in short bursts so slower apps have time to render their menu before we calculate position. Second, the `_best_position()` function was rewritten to calculate the exact clamped position for each of the four directions, verify it does not overlap the menu after clamping, and try the next direction if it does. Third, the fallback (for apps where no menu window is found) was rebuilt using Windows' predictable menu placement rule: the menu always opens away from the nearest screen edge, so the button is placed on the opposite horizontal side of the cursor. A dead zone (centre 20% of screen width and height) was also identified where prediction is unreliable — in that zone the button always appears to the left of the cursor regardless of other conditions.

**Files changed:** `src/context_menu.py`

---

### 🐛 Bug 8 — "Paste from ClipDrop" in Explorer Does Nothing

**Status:** ✅ Resolved

**What happened:**
Clicking "Paste from ClipDrop" from the Windows Desktop or File Explorer right-click menu produced no response — no popup appeared and no error was shown.

**Root cause:**
The Windows Registry command correctly fired when clicked, writing a signal file (`clipdrop.signal`) to the temp folder containing the cursor position. However, the running ClipDrop app had no code watching for that file. The signal was written and silently ignored.

A secondary issue was that `pyautogui.position()` writes its output as `Point(x=1204, y=540)` rather than a plain `(1204, 540)` tuple string, causing the position parser to crash when it eventually was implemented.

**How it was fixed:**
A background thread (`_watch_signal_file`) was added to `context_menu.py`. It polls the temp folder every 200ms for the signal file. When found, it reads the position using regex to correctly parse the `Point(x=..., y=...)` format, deletes the file, and triggers the ClipDrop popup at that position.

**Files changed:** `src/context_menu.py`

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
| 2026-05-25 | Bug 6 fixed — overlay no longer closes native context menu (removed focus_force) |
| 2026-05-25 | Bug 7 fixed — overlay button positioning overhauled with retry logic, border math, and dead zone handling |
| 2026-05-25 | Bug 8 fixed — "Paste from ClipDrop" in Explorer now triggers popup via signal file watcher |
| 2026-05-30 | UI framework migrated from tkinter to PyQt6 — all 5 UI files rewritten |
| 2026-07-19 | Stability pass — threaded paste, crash fixes, popup persistence, side-panel actions, live settings |
| 2026-07-20 | Visual overhaul — floating rounded cards with shadows, gradient surfaces, accent scrollbars, fluid hover motion, live in-place updates |
| 2026-07-20 | Interactivity update — shortcuts manager with 5 rebindable global hotkeys, snippet scratchpad, Ctrl+click multi-selection with combined paste, drag & drop out, smarter overlay button positioning, profile-switch and context-menu stability fixes |
| 2026-07-21 | Trigger modes — six ways to summon the popup (double right-click default, middle-click, side button, Ctrl+right-click, overlay button, hotkey-only); 3-tier context-menu detection (native / Chromium / UI Automation); instant overlay hide on menu close |
| 2026-07-21 | Icon system rebuilt as SVG (crisp at every size), dedicated Python icon and smart type detection, plus an optional per-extension "Labeled documents" icon pack selectable in Settings |
| 2026-07-21 | Adjustable sizing — three sliders (main window, row size, side list) scaling the UI 60–120% in fixed 10% steps, with dependent values derived automatically |
| 2026-07-21 | Open items from the list — right-click Open / Open containing folder for files, folders and links, with existence checking moved off the UI thread so dead network paths can't freeze the app |
| 2026-07-22 | Customisation pass — cursor positioning fixed on scaled displays, hover bulge + selectable hover colours + font-size control, side-list-rows slider, shortcut unassign, and create-new-profile in every send-to menu and the header |

---

## About This Project

ClipDrop is being built by **Cosmas** as a first software development project — going from idea to a working, polished application. The goal is to learn by building something genuinely useful.

---

*Built with passion. Designed for simplicity.*

---

### 🔧 Migration — tkinter → PyQt6 (May 2026)

**Status:** ✅ Complete

#### What changed

All UI files were rewritten from tkinter to PyQt6. Business logic files were not touched.

| File | Before | After |
|---|---|---|
| `src/main.py` | `tk.Tk()` + `root.mainloop()` | `QApplication` + `app.exec()` |
| `src/dropdown_popup.py` | tkinter `Toplevel` + `Canvas` | `QWidget` + `QListWidget` |
| `src/context_menu.py` | tkinter `Toplevel` overlay | `QWidget` overlay + Qt signals |
| `src/tray_icon.py` | `pystray` library | `QSystemTrayIcon` |
| `src/settings_panel.py` | tkinter `Toplevel` | `QDialog` |

Files left untouched: `clipboard_watcher.py`, `history_manager.py`, `profile_manager.py`.

#### Why tkinter was replaced

After extensive development, several bugs proved impossible to fix without changing the framework:

**Side panel had no real-time updates.** Pin and delete actions in the multi-file side panel did not update visually without closing and reopening the panel. Every attempted fix — canvas `delete("all")` + redraw, closure-captured rebuild functions, instance-level panel tracking — either failed silently or introduced new regressions.

**Popup flickered on every interaction.** `_refresh()` had to destroy and rebuild the entire popup window to reflect any data change (pin, delete, move). This caused visible flicker on every user action.

**Event propagation bugs.** `<ButtonRelease-1>` events bubbled from pin/delete buttons up to the row, triggering unintended paste actions. Requires manual `"break"` returns on every binding — fragile and kept regressing.

**Threading constraints.** tkinter is single-threaded. All UI updates must be marshalled through `root.after()`, making real-time updates from the clipboard watcher thread unnecessarily complex and error-prone.

**Focus and borderless window issues.** `overrideredirect` popup windows on Windows have unreliable focus and event routing, requiring increasingly complex workarounds that kept breaking across different scenarios.

The root cause of all these issues is architectural: tkinter has no concept of partial widget updates. To reflect any structural change (reordering, deletion) you must either rebuild the entire widget tree — causing flicker — or use canvas `itemconfigure` — which only works for visual properties, not structure. Neither approach was sufficient.

#### Why PyQt6 was chosen

PyQt6 solves every one of these issues natively:

- **Real-time list updates** — `QListWidget` updates individual rows in-place via signals. No destroy/rebuild ever needed.
- **Clean event model** — signals and slots replace tkinter's fragile binding system. Event propagation is explicit and reliable.
- **Thread-safe signals** — the clipboard watcher can emit signals from its own thread; Qt automatically marshals them to the UI thread.
- **Native Windows integration** — `QSystemTrayIcon`, `QMenu`, clipboard API, hotkey registration all built-in.
- **Borderless windows** — `Qt.FramelessWindowHint` works correctly on Windows without the focus issues of `overrideredirect`.

PyQt6 was chosen over alternatives (Dear PyGui, Flet, Kivy, wxPython) because ClipDrop is a Windows OS utility that requires deep native integration — system tray, clipboard API, global hotkeys, and borderless cursor-positioned windows — all of which PyQt6 handles natively.

---

### 🎨 Visual Overhaul & Stability Update (July 2026)

**Status:** ✅ Complete

A full polish pass over the PyQt6 UI: modern depth, fluid motion, live
in-place updates, and a set of hard-won stability fixes.

#### Visual upgrade — three phases

**Phase 1 — Elevation.** The popup and all side panels are now floating
rounded cards with real drop shadows, drawn into transparent window
margins (DWM shadows don't render on layered windows, so Qt paints
them). The settings window's native title bar follows the app theme —
dark theme, dark title bar — via the Windows DWM API.

**Phase 2 — Surfaces.** Headers use vertical gradients with a dark seam
at the base (raised-surface look). Buttons have gradient faces, hover
brightening, and a pressed state that darkens and shifts the label 1px
down. The search field is a recessed inset channel. Scrollbars are slim,
rounded, and accent-coloured so they're visible even at rest — brighter
on hover, lightest while dragging.

**Phase 3 — Motion.** Row hover runs on an eased animation curve
(OutExpo — instant response, soft landing) driving background tint,
accent-strip growth, and text brightening together. All data actions
(pin, delete, move, profile switch) update the open popup **live and
in-place** — the window is never destroyed and rebuilt.

#### Interaction upgrades

- The popup stays open through pin / delete / move / profile actions
  and pasting — it closes only on outside click or `Escape`
- Optional **hover-to-close** mode (close the popup by moving the mouse
  away) selectable in Settings
- Paste runs entirely on a worker thread — the UI never freezes,
  even while pasting large images
- Paste-target validation: pasting raw text into File Explorer or the
  desktop shows a clear error instead of failing silently; images
  pasted there become PNG file copies automatically
- Multi-file side panel: per-file right-click menu (Send to profile /
  Pin / Delete), panel-specific pins with red pin markers, hover-reveal
  of folder contents in a nested panel, and item counts on every
  folder row
- All-new icon set rendered at 4× supersampling for crisp edges:
  Office-style letter tiles, PDF tile, DLL gear, chain-link URLs,
  globe HTML, and live colour swatches for copied hex colour codes
- In-app toast notifications for every action (paste confirmations
  with the item name, errors, profile sends) — subtle, 1.5 s max

#### Notable bugs fixed along the way

**Frozen UI during paste.** The entire paste sequence (clipboard write,
focus handling, `Ctrl+V`, watcher resume) ran on the UI thread with
built-in delays — about one full second of frozen interface per paste.
It now runs on a dedicated worker thread with signal-based error
reporting; the UI thread never sleeps.

**Hard crash when clicking a file in the side panel.** Clicking a file
tore down the panel's widget tree synchronously — from *inside* the
panel's own mouse-release handler. The native widget was destroyed
while its event code was still on the stack (use-after-free), killing
the process with no traceback. Fix: the action is deferred one
event-loop turn so the stack unwinds before teardown. Rule adopted
project-wide: never destroy a widget tree from inside its own event
handler.

**Popup closing on its own menus.** The global click monitor treated
clicks in ClipDrop's *other* windows (side panels, context menus) as
"outside" clicks and hid the popup — each new window type reintroduced
the bug. The hit test now asks Windows which process owns the clicked
window: any ClipDrop-owned window counts as inside. Fixed permanently
for all current and future windows.

**Rows rendering white after the card restyle.** Scoping the window's
stylesheet to the new rounded card silently removed the background
cascade that child widgets depended on, and Qt does not paint stylesheet
backgrounds on QWidget subclasses unless explicitly told to
(`WA_StyledBackground`). Rows and the list container now paint their
own backgrounds.

**Pin/delete flicker.** Any data change rebuilt the entire popup
window — a visible blink. `_refresh()` now updates rows, header counts,
and window height inside the existing window (the same machinery the
live search filter uses); a full rebuild happens only on theme changes.

**Search box not accepting input.** The popup deliberately never takes
keyboard focus (`WS_EX_NOACTIVATE`) so pastes land in the target app —
which also blocked typing in search. Clicking into the search field now
activates the window on demand, and the paste worker re-foregrounds the
original target before sending `Ctrl+V`, so pasting still lands in the
right place after a search.

---

### ⚡ Interactivity & Shortcuts Update (July 2026)

**Status:** ✅ Complete

A major interactivity pass: configurable global shortcuts, multi-item
workflows, drag & drop, and another round of hard-won stability fixes.

#### Shortcuts manager

A dedicated **Shortcuts window** (Settings → Manage Shortcuts…) where
every global hotkey is rebindable. Click the ⏺ listen button — it pulses
while capturing — press your combination, Save applies live. Guard
rails: duplicate assignments are refused with the owning action named,
well-known Windows combos (Copy, Alt+Tab, Task Manager…) trigger an
"already in use" warning before you steal them, failed bindings roll
back to the previous working combo, and every shortcut has a one-click
reset to default.

| Action | Default |
|---|---|
| Open ClipDrop popup | `Ctrl+Shift+V` |
| Pause / resume clipboard capture | `Ctrl+Shift+P` |
| New snippet (blank scratchpad) | `Ctrl+Shift+N` |
| Clear all history (with confirmation) | `Ctrl+Shift+H` |
| Switch to next profile | `Ctrl+Shift+O` |

#### Snippet scratchpad

`Ctrl+Shift+N` opens a blank editor window anywhere. Type a note or a
code fragment, hit Save (or `Ctrl+S`) — it lands in the clipboard
history like any copied item: pasteable, pinnable, searchable,
assignable to profiles, and auto-classified (code, hex colour, URL,
plain text).

#### Multi-selection & combined paste

`Ctrl+click` toggles items into a multi-selection in **every** list —
main popup, file side panels, nested folder panels. Selected rows show
an accent outline; the header count becomes a clickable **✕ N selected**
badge that clears the selection, and `Escape` steps back through
side-panel selection → main selection → close. Clicking any selected
row pastes the **whole selection as one payload**: text items joined
line-by-line, files merged into a single multi-file paste. Selection
survives live list refreshes and resets when the popup closes.

#### Drag & drop out of ClipDrop

Drag any main-list row into another app: files and images travel as
real file URLs (drop on Explorer to copy them), text drops into
editors and forms. Dragging a selected row carries the entire
selection — the drag image shows a count bubble. Auto-close timers
stand down while a drag is in flight, so the source window can never
be destroyed mid-drag.

#### Smarter "Paste from ClipDrop" button

The floating right-click button was rewritten around a simple rule:
**anchor at the cursor, hug the context menu's border**. When the
app's menu is detected, the button sits just outside the menu edge
nearest the click, at cursor height. When it isn't, the button sits
beside the cursor on the side the menu won't occupy. Every placement
clamps to the monitor the click happened on, taskbar excluded — no
more drifting across the screen or landing on the taskbar.

#### Notable fixes in this update

**System-wide drag lag.** The global mouse hook ran Python for every
mouse event on the system — including every mouse-move — adding cursor
latency that made OS drag-and-drop stutter badly. The hook now bails
on anything but the two button events it needs, at the cost of a
single integer comparison.

**Stuck context menus.** Right-click menus opened from the popup could
ignore outside clicks and even outlive the app on screen. Menus from a
no-activate window can't establish their dismissal grab — they are now
parented to the popup (they die with it) and the owner window is
activated just before the menu opens.

**Frozen profile switching.** Switching profiles could freeze the popup
on the previous profile's content. Two root causes: partial repaints of
a translucent window were rejected by Windows when the drop shadow's
repaint region overflowed the window bounds (shadow blur must fit
inside the transparent margins — now an enforced invariant), and the
window height was computed from a stale layout hint (now derived
exactly from a chrome-height measurement taken at build time).

**Send to General.** The right-click "Send to profile" menus — main
list, side panels, nested panels — now include General everywhere it
makes sense; sending a side-panel file there creates its own visible
history entry.

---

### 🎯 Trigger Modes & Context-Menu Handling (July 2026)

**Status:** ✅ Complete

This update reworks *how ClipDrop is summoned* on a right-click, and it
was the result of chasing a problem that turned out to be unwinnable in
its original framing.

#### The problem

ClipDrop needs to offer "Paste from ClipDrop" wherever you right-click.
On the Windows Shell (Desktop, File Explorer) it injects a real entry
into the native menu through the registry — clean and native. But every
other app builds its **own** right-click menu and allows no external
injection. For those, ClipDrop floated a small "📋 Paste from ClipDrop"
button near the cursor.

That button kept **overlapping the app's own context menu**. The fix
seemed obvious — measure the menu's rectangle and place the button just
outside its border — so the detection was built out in three tiers:

1. **Native menus** (window class `#32768`) — Explorer, classic apps.
   Measured exactly.
2. **Chromium / Electron popup windows** (Chrome, VS Code, Discord) —
   real top-level windows but with app-specific classes, identified by a
   heuristic (visible borderless popup, menu-like proportions, adjacent
   to the click, owned by the foreground app).
3. **In-page menus** (the Claude app, Slack, web apps) — drawn as HTML
   *inside* the app's own window, with **no window handle at all**. The
   only way to read their bounds is Windows **UI Automation** (the
   accessibility tree), queried for an open `Menu` element near the
   click. (Adds the `comtypes` dependency.)

The overlay button placement was also rewritten to **anchor at the
cursor and hug the menu's nearest border**, clamped to the monitor the
click happened on (an earlier version drifted across the screen and even
onto the taskbar).

#### The breakthrough — stop fighting the menu

Even with three tiers, detection can't be universal: some apps expose
nothing to accessibility, and their accessibility layer wakes *lazily*,
so the first right-click in a fresh app misses. When detection fails,
placement is a guess — and web menus open in any direction, so the guess
sometimes lands right on the menu. **A cursor-anchored button has an
irreducible overlap rate: when you can't measure the menu, you can't
reliably avoid it.**

The insight was to change the question. The overlap only exists because
the trigger *is* the right-click — the same gesture that opens the menu
we're trying to dodge. Trigger ClipDrop with a **different** gesture and
there is no button to overlap, in any app, ever — no detection required.

So the overlay button became one option among several **trigger modes**
(Settings → Popup trigger):

| Mode | How it fires | Menu flash |
|---|---|---|
| **Double right-click** (default) | Two quick right-clicks | brief |
| **Middle-click** | Press the scroll wheel | none |
| **Mouse side button** | A thumb Back/Forward button | none |
| **Ctrl + right-click** | Hold Ctrl, then right-click | none |
| **Overlay button** | Button appears on right-click | — |
| **Hotkey only** | Keyboard shortcut only | — |

Every gesture-based mode opens the popup directly at the cursor with the
correct paste target (captured on the click, before any menu steals
focus). The click is **swallowed cleanly** — both button-down and its
matching up — so the app never sees a half-click. Only double-right-click
briefly flashes the native menu (its first click is a normal right-click
by design); an Escape dismisses it as the popup opens. The others open
with no flash at all.

#### Known trade-offs (documented, not bugs)

- **Middle-click / side button** override that button's normal use
  (open-in-new-tab, Back/Forward) while the mode is active — the cost of
  a dedicated one-hand trigger.
- **Admin/UIPI:** a normal-privilege ClipDrop can't overlay or trigger
  over apps running as Administrator. See *Known Limitations*.
- **Instant hide:** when the overlay button mode is used, a WinEvent hook
  now hides the button the moment its native menu closes (submenu-safe
  via a nesting count), instead of lingering on the fallback timer.

---

### 🖼️ Icon System & Optional Icon Packs (July 2026)

**Status:** ✅ Complete

Every file-type icon was rebuilt as **SVG**, and icons became
**selectable packs** so users can pick the look they prefer.

#### Why the icons were rebuilt

The original icons were drawn shape-by-shape with PIL drawing primitives
— rectangles, ellipses, lines. That approach has a hard ceiling: PIL
can't draw smooth bezier curves or gradients, so anything organic (a
logo, a gear, a globe, a chain link) came out blocky no matter how much
it was tuned. Supersampling helped the edges but couldn't fix the
shapes themselves.

The fix was to stop drawing and start **rendering**: icons are now
authored as SVG and rasterised by Qt's own SVG engine (`QSvgRenderer`)
at whatever size is needed. Curves, gradients and fine detail survive
all the way down to the 16 px side-panel size. No new dependency —
`QtSvg` ships with PyQt6.

#### One constraint worth knowing

**Qt's SVG renderer cannot draw `<text>` elements.** This was confirmed
by testing, and it shapes the whole design:

- Icons that are a coloured tile plus a letter (Word "W", Excel "X",
  PowerPoint "P", PDF, the clipboard-text "Aa", the hex "#") keep using
  **PIL**, which loads the bold TTF directly and renders crisp glyphs.
- Everything else — the Python logo, gears, globe, chain link, folder,
  waveform, terminal — is **pure SVG**.

The result is a hybrid that uses each tool where it is strongest.

#### Smart type detection

File types resolve to icons through an extension map, with dedicated
treatment where it matters:

- **`.py` / `.pyw` / `.pyi`** get a real Python icon (the interlocking
  two-tone logo) rather than the generic code icon, plus their own
  Python-blue accent stripe.
- **Hex colour codes** copied as text render a live swatch of the actual
  colour, with the `#` in black or white depending on the colour's
  luminance.
- Unrecognised extensions fall back to a generic document icon — an icon
  can never render blank, and a drawing error can never crash the app.

#### Optional icon packs

Settings → **Icon pack** now offers two complete sets:

| Pack | Style | Granularity |
|---|---|---|
| **Default ClipDrop** | Colourful modern icons — Office letter tiles, Python logo, gears, globe | per file category |
| **Labeled documents** | Document page + glyph + extension badge (PDF, DOCX, PNG…) | per file **extension** |

The Labeled pack renders a distinct icon for every extension — PNG, JPG,
GIF and SVG all differ, as do MP4 and MOV. Its badges are composited
with PIL after the SVG shape is drawn, since Qt drops SVG text.

Three types are **pinned to the Default icons in every pack**, by
preference: **Python**, **shell/bash**, and **clipboard text**. Any
extension a pack doesn't define falls back to the Default set, so no
icon is ever missing. Switching packs applies immediately to an open
popup.

---

### 📐 Adjustable Sizing (July 2026)

**Status:** ✅ Complete

Settings → **Sizing** lets the user scale the interface with three
sliders, each running **60% to 120% in fixed 10% steps**, where 100% is
the app's default size:

| Slider | Scales |
|---|---|
| **Main window** | popup width and the preview text wrap width |
| **Row size** | row height, row icon, and the list height cap |
| **Side list** | side panel width, row height, font, and row icons |

#### Deliberately coarse

The steps are fixed rather than free-form on purpose. Each slider works
internally in 10% units (positions 6–12), so **every position it can
reach is a valid size** — there is no snapping logic and no way to land
on a broken layout. Stored values are defended too: anything out of
range clamps to 60/120, off-step numbers snap to the nearest step, and
an unreadable value falls back to 100%.

#### Values that move together are derived, not exposed

Adding a slider for every measurement would let users create layouts
that look wrong — a wide window with narrow text, or tall rows with tiny
icons. So the dependent values are computed from the three sliders
instead:

- the row **icon** scales with row height
- the preview **text wrap width** scales with window width
- the list **height cap** scales with row height, so roughly the same
  number of rows stays visible at any size
- the side list's **font and row icons** scale with the panel

#### Applying

Sliders live-apply through the popup's normal rebuild path, debounced by
180 ms so dragging across several steps rebuilds once when the user
settles rather than on every step. The exact-height layout machinery
(measuring the window's fixed "chrome" and computing height from the row
count) absorbs the new sizes automatically.

The section is intentionally compact — three single-line rows — because
at this window width per-row captions wrap to several lines and would
triple the height of the section for no added clarity.

---

### 📂 Open Items From the List (July 2026)

**Status:** ✅ Complete

Right-clicking an item now offers **Open** and **Open containing
folder**, in both the main list and the file side panels.

| Item | What Open does |
|---|---|
| Single file | Launches it with its default app |
| Folder | Opens it in Explorer |
| Multi-file entry | *Reveal only* — never opens dozens of files at once |
| Image | Opens the PNG ClipDrop saved for it |
| URL | Opens it in the default browser |
| Text / code / hex | No Open entries — there is nothing to open |

#### The hard part: checking whether the file still exists

Clipboard history is persistent, so entries routinely point at files
that have since been moved, renamed or deleted — or that live on a drive
which is no longer attached. Verifying that is not free:

> `os.path.exists()` on a **disconnected network share, an unplugged USB
> drive or a sleeping NAS blocks for seconds** while Windows waits out
> its timeout.

Doing that check on the UI thread would freeze the entire app — and it
would freeze it precisely when building a right-click menu, which is the
worst possible moment. So the rule here is absolute: **the UI thread
never touches the filesystem.**

- **Building the menu** uses string operations only (splitting an
  extension, counting a list). The menu appears instantly even for an
  item pointing at a dead network path.
- **Existence checking and launching** happen on an `_OpenWorker` thread.
  If the file is gone, the worker reports back and the user gets a clear
  toast — *"⚠ No longer exists: report.pdf"* — instead of a silent
  failure or a Windows error dialog.

This was verified against an unroutable UNC path: the call returned in
under 0.15 s while the worker sat blocked for the full SMB timeout.

#### Opening an executable runs it

A misclick in a list is far easier than a deliberate double-click in
Explorer, so Open on `.exe`, `.msi`, `.bat`, `.ps1`, `.vbs`, `.lnk` and
similar asks for confirmation first. The check is on the extension
string, so it costs nothing and never touches the disk. *Open containing
folder* never triggers it.

#### Shutdown safety

Destroying a running `QThread` aborts the process — and a dead network
path can legitimately keep a worker busy for the whole timeout. Quitting
ClipDrop shortly after opening a stale network file would therefore have
crashed on exit, so in-flight checks are given a moment to finish during
shutdown.

---

### 🎛️ Customisation & UX Refinements (July 2026)

**Status:** ✅ Complete (window drag-resize still to come)

#### Cursor positioning on scaled displays

The popup opens **at the cursor**, but on a display with Windows scaling
(125%, 150%) it was landing offset. The cause is a coordinate-space
mismatch: the mouse hook reports **physical** pixels while Qt positions
windows in **logical** pixels, and on a scaled screen those differ by the
scale factor. The fix anchors the popup on `QCursor.pos()` — Qt's own
reading of the cursor — so the anchor and the placement call are in the
same coordinate system and always agree, at any scaling.

#### Appearance options

- **Row hover** was redrawn with a mild convex "bulge": a vertical
  gradient (lighter top, darker base) that reads as a slightly raised
  surface. Its contrast was raised too — the light theme's near-invisible
  grey hover became a clear indigo tint.
- **Hover colour** is now selectable — Indigo (default), Gold, Emerald,
  Rose, Sky, Violet, Slate.
- **Main-window font size** is adjustable (80–140%).
- The **transparency** floor was raised to 50% (below that the popup was
  too faint to read).

#### Sizing

The side-list *size* slider was replaced with a **Side list rows** slider
(1–20) — how many rows show before it scrolls — which is the dimension
that actually matters for a hover flyout. Row size and main-window sliders
remain (the main-window one until window drag-resize replaces it).

#### Shortcuts — unassign

Each shortcut row now has three actions: **listen**, **reset to default**,
and **clear**. Clearing leaves the action with *no* shortcut: an empty
combo is saved as "unassigned" and stays that way (it no longer silently
reverts to the default on the next launch).

#### New profile, in every menu

A profile can be created on the spot — a **➕** in the popup header (new
empty profile, switches to it) and a **➕ New profile…** entry in every
"Send to profile" menu: the main list, the file side panel, and the nested
folder panels. From a Send-to menu it prompts for a name, creates the
profile, and drops the clip straight into it.

