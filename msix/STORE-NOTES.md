# Microsoft Store submission notes — Stacka Clipboard

Reference for the Partner Center submission. Not user documentation.

## Identity (from Partner Center → Product identity)

| Field | Value |
|---|---|
| Package/Identity/Name | `CosmasNwachukwu.StackaClipboard` |
| Package/Identity/Publisher | `CN=5772570D-DDFD-4FD2-967F-B4ADBD34BC29` |
| PublisherDisplayName | `Cosmas Nwachukwu` |

These must match `msix/AppxManifest.xml` exactly or the upload is rejected.
**Version:** four parts with the last always `0`. Bump the third for each new
submission — `1.0.0.0` → `1.0.1.0` → `1.0.2.0`.

## Signing

The `.msix` is uploaded **unsigned**. Microsoft signs it during certification
with the Store certificate — that is what makes this the zero-cost path to a
signed, SmartScreen-clean build.

To test the package on this machine before submitting, sign it with a
self-signed certificate and trust that certificate locally. An unsigned MSIX
cannot be installed.

## Restricted capability: `runFullTrust`

Every packaged desktop (Win32) app declares this, and Partner Center asks for a
justification. Suggested wording:

> Stacka Clipboard is a Win32 desktop application built with Python and PyQt6.
> It requires full trust to read and write the Windows clipboard, to save its
> history to the user's local AppData folder, and to run as a background tray
> application. It does not use the network and sends no data anywhere.

## Expect a question about the global mouse hook

The app installs a low-level mouse hook (`SetWindowsHookEx` / `WH_MOUSE_LL`) so
the user can summon the clipboard popup anywhere with a mouse gesture — a double
right-click, middle-click, side button, or Ctrl+right-click. This is the same
technique input-utility software uses, and it is the app's core feature, but it
is also a pattern certification looks at closely. Be ready to explain:

- The hook only reacts to the two button events it needs and ignores everything
  else, including mouse movement.
- It does not log, store, or transmit input. Nothing leaves the machine.
- The trigger is user-configurable and can be switched off entirely
  (Settings → Popup trigger → "Hotkey only").

Global keyboard shortcuts are registered for the same reason (open the popup,
pause capture, clear history, switch profile) and are equally configurable.

## Privacy

- All data stays on the device: clipboard history, profiles and settings live in
  `%APPDATA%\Stacka` (a packaged build redirects this into its own app-data
  location).
- No network calls, no telemetry, no accounts.
- History and profiles are **encrypted at rest with Windows DPAPI**, tied to the
  signed-in user account.
- Detected credit-card numbers are masked in the UI (`Visa •••• 4242`) and the
  real number is stored encrypted, decrypted only in memory to paste.
- The "Support" button opens an external donation page in the user's browser and
  transmits no app data.

A privacy policy URL is required for the listing; the statements above are what
it needs to cover.

## Known difference from the GitHub build

The **"Paste from Stacka" File Explorer entry is not present in the Store
build.** MSIX virtualizes the registry, so the keys the app writes at runtime
never reach Explorer, and declaring a package context menu requires a COM
`IExplorerCommand` handler (a native DLL) — out of scope here.

Impact is small: the mouse-gesture triggers and the global hotkey work
everywhere, including Explorer and the Desktop, and the default trigger is
already double right-click. The GitHub installer build keeps the shell entry.

### If it turns out users want it — the three routes

1. **`unvirtualizedResources`** (restricted capability). Switches registry
   virtualization off for the package, so the keys the app already writes at
   runtime would reach the real Explorer — no code change. Cheap and
   reversible, but Microsoft must approve the capability at submission, so it
   risks a certification round-trip. Try this first, in an update, not on the
   first submission.
2. **A native `IExplorerCommand` COM DLL** — the way Microsoft intends, and the
   only one that also puts the entry in the *main* Windows 11 menu rather than
   under "Show more options". Costs a C++ component, an MSVC toolchain and
   permanent maintenance in an otherwise pure-Python project.
3. **Submit the Win32 installer instead of MSIX** — keeps the registry entry as
   it is today, but the Store does not re-sign EXE/MSI submissions, so it needs
   a purchased code-signing certificate.
