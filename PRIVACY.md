# Privacy Policy — Stacka Clipboard

**Last updated:** 26 July 2026

Stacka Clipboard ("Stacka") is a free, open-source clipboard manager for
Windows, developed by Cosmas Nwachukwu.

## The short version

**Stacka has no servers, no accounts, and no internet connection.** Everything
it stores stays on your own computer. Nothing you copy is ever sent anywhere,
to the developer or to anyone else.

## What Stacka stores

Stacka's purpose is to remember what you copy, so it necessarily keeps a
history of it. While Stacka is running it records, **on your device only**:

- **The content you copy** — text, links, code, colour codes, file paths, and
  images.
- **Where it came from** — the name or window title of the app you copied from
  (for example *"report.docx (Word)"*), shown so you can recognise a clip.
- **Your settings** — theme, language, size, shortcuts, and your profiles.

Stacka does **not** record what you type. Its keyboard shortcuts and mouse
gestures are used only to detect the specific combinations you have chosen to
open the app; no other keystroke or mouse activity is examined, stored, or
transmitted.

## Where it is stored, and how it is protected

Everything lives in a single folder on your computer — `%APPDATA%\Stacka`
(the Microsoft Store version uses its own equivalent per-user location).

- **Your clipboard history and profiles are encrypted at rest** using
  **Windows DPAPI**, which ties the encryption to your Windows user account.
  Another account on the same machine, or someone who copies the files to a
  different computer, cannot read them.
- **Copied images are saved as ordinary PNG files** in that folder and are
  **not** encrypted. If that matters to you, remove image clips you consider
  sensitive.
- **Detected payment card numbers** are handled specially: the list only ever
  displays a masked form (for example `Visa •••• 4242`), the full number is
  encrypted before it is written to disk, and it is decrypted only in memory
  at the moment you paste it.
- **A diagnostic log** (`stacka.log`) records app events such as startup and
  errors. It deliberately contains **no clipboard content and no clip
  details** — not the text you copied, not window titles, not file paths.

Because this data is protected by your Windows account rather than a separate
password, it does **not** protect against someone using your computer while you
are signed in, or against software already running as you.

## What Stacka sends — nothing

Stacka makes no network requests. It has no telemetry, no analytics, no crash
reporting, no update check, and no account system. The developer receives
nothing about you or your use of the app, and cannot: there is nowhere for it
to go.

The only time anything leaves Stacka is when **you click a link yourself**:

- **"Support Stacka"** opens a donation page (Paystack) in your normal browser.
- **"Open link"** on a copied URL opens it in your normal browser.
- The **GitHub links** in Settings open in your normal browser.

In each case Stacka simply hands the address to your browser. It sends no clip
data, no identifier, and nothing about you. Once your browser opens those
sites, their own privacy policies apply.

## Deleting your data

You are always in control of it:

- **Remove** any individual clip from the list.
- **Clear All History** (Settings, or the tray menu) empties everything.
- **Auto-wipe** (Settings → History) clears your history automatically on a
  schedule you choose — daily, weekly, monthly, quarterly or yearly. Pinned
  items are kept.
- **Uninstalling** removes the app; it asks whether to delete your clipboard
  data and keeps it unless you say otherwise. You can delete the
  `%APPDATA%\Stacka` folder yourself at any time.

## Children

Stacka is a general-purpose desktop utility. It is not directed at children and
collects no personal information from anyone.

## Changes

If this policy changes, the updated version will be published at this address
with a new "last updated" date.

## Contact

Questions about privacy in Stacka:

- **Email:** finecosmas@gmail.com
- **Source code and issues:** https://github.com/Darkchild123/Stacka-Clipboard

Stacka is open source under the GNU General Public License v3.0 — every claim
on this page can be checked against the source.
