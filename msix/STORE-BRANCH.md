# The `store-version` branch

This branch is the **paid Microsoft Store edition** of Stacka. Everything to do
with publishing to the Store belongs here and nowhere else.

## How it differs from `full-version`

| | `main` / `full-version` | `store-version` |
|---|---|---|
| Audience | Anyone downloading from GitHub | Microsoft Store customers |
| Price | Free | Paid, with a free trial |
| Support / donate button | Yes — in Settings ▸ About and the popup footer | **Removed** |
| `src/donate.py` | Present | **Deleted** |
| Explorer shell entry | Yes (registry) | Not available — MSIX virtualizes the registry |
| Store submission material | — | Lives here |

`full-version` stops at building the MSIX. Store listing work, submission
notes, pricing and trial configuration all continue on this branch.

## The trial is NOT built into the app

Microsoft handles it. Configure it in Partner Center under
**Pricing and availability → Free trial**; the Store enforces it server-side.
Do not add licence checks, expiry timers or phone-home code to the client:

- The app is GPL-3.0, so any such check is visible in the source and can be
  removed and rebuilt by anyone.
- It would contradict `PRIVACY.md`, which states — accurately, and as a
  selling point — that Stacka makes no network requests.
- A clipboard manager with a global mouse hook that also calls home looks,
  feature for feature, like a keylogger to antivirus heuristics.

## Licence reality, so it is not relitigated later

GPL-3.0 **permits selling** ("You may charge any price or no price for each
copy that you convey"). What it forbids is closing the source. So:

- Selling on the Store is entirely legitimate.
- It cannot be **exclusive**. Buyers are entitled to the source, may rebuild
  it, and may redistribute it — the free build is public on GitHub anyway.
- The paid proposition is therefore **convenience and support**: signed, one
  click, automatic updates, no SmartScreen warning, and it funds development.
  It is not "paying unlocks the app".

## Keeping this branch up to date

Code fixes land on `full-version` first, then come here:

```
git checkout store-version
git checkout full-version -- src/
# then re-apply the Store-only removals:
#   * delete src/donate.py
#   * drop the "from donate import ..." line in dropdown_popup.py and settings_panel.py
#   * remove the Support label from the popup footer (_build / footer strip)
#   * remove the Support button at the end of _section_info in settings_panel.py
```

Each removal is marked in the source with a `STORE BUILD:` comment, so they
are easy to find after a sync.
