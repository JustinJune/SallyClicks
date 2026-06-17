# Sally Clicks!

A natively-injected macOS macro recorder with a clean multi-slot UI.

Record mouse clicks and keystrokes, save them, chain them together, and replay
with absolute-time precision. Built exclusively for macOS using the Quartz
CGEventTap API for zero-drift playback and true OS-level input injection.

---

## Features

### Precision Playback

- **Absolute-time scheduling** — zero drift, even on long or complex macros
- **True key holds** — records exactly how long each key was held and replays it faithfully
- **Speed scaling** — replay at 0.5×, 1×, 2×, 4×, or 8×
- **Loop control** — set a repeat count or loop infinitely with a live countdown

### Multi-Slot Workspace

- **8 independent slots** — run up to 8 distinct macros side by side in one window
- **Stitch** — drag and drop any combination of slots to chain them into a single macro
- **Session save / load** — save your entire workspace (all slots, hotkeys, and settings)
  and restore it in one click

### Session Portability

When saving a session you choose one of two modes:

| Mode | Behaviour |
|------|-----------|
| **Portable** | Plain JSON secured with a SHA-256 checksum. Share freely between Macs. |
| **Locked to this Mac** | Fernet AES-encrypted and HMAC-signed. Cannot be opened on another machine. |

Individual macro files (`.json`) are always portable.

### Safety

- **Password guard** — queries the macOS Accessibility API before recording starts;
  warns if a secure text field is focused in another app
- **Escape hatch** — hold Escape for 2 seconds to kill all playback and release
  all held keys, even if the UI thread is frozen
- **File integrity** — all files are checksum or HMAC-signed; tampered files are
  refused on load with a clear explanation
- **Duplicate hotkey detection** — the Hotkey Manager prevents you from assigning
  the same key combination to more than one action
- **Minimum event delay** — a 1 ms floor between injected events prevents
  accidental input storms from zero-delay macros
- **Secure Lock encryption** — users can opt to securely lock individual macros or entire workspaces using AES-256 encryption, mathematically binding the file to their specific Mac's hardware UUID to prevent cross-device execution.
---

## Installation

Requires macOS 12 (Monterey) or later and Python 3.10+.

```bash
git clone https://github.com/JustinJune/SallyClicks
cd SallyClicks
python -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
python main.py
```
## Building a Standalone App (Optional)

If you prefer not to run the application from the terminal every time, you can compile into a native macOS `.app` bundle using PyInstaller. This bundles the Python interpreter and all dependencies into a single, double clickable application.

**1. Install PyInstaller**
Ensure your virtual environment is activated, then run:
```bash
pip install pyinstaller
pyinstaller --windowed --noconfirm --name "Sally Clicks" main.py
```
---

## Accessibility Permission

Sally Clicks requires Accessibility access to record and inject input system wide.

1. Open **System Settings → Privacy & Security → Accessibility**
2. Click **+** and add your Terminal app (or whichever app you launch Python from)
3. Re-launch Sally Clicks

**Why is this needed?**
Sally Clicks uses macOS's CGEventTap API — the same mechanism used by assistive
technology and professional automation tools — to observe and inject keyboard and
mouse events at the OS level. Without this permission, recording and playback
cannot function.

---

## Privacy

**Local only** — Sally Clicks never sends data over the network. All recordings
stay on your machine.

**Do not record passwords.** When recording is active the event tap sees all
keyboard input system-wide. Sally Clicks will warn you if it detects a password
field is focused, but this detection is best-effort. Anyone with access to your
`.json` files can read the inputs recorded in them.

The `.gitignore` in this repo excludes `*.json` so you cannot accidentally
commit macro or session files to a public repository.

---

## Controls

| Action | Method |
|--------|--------|
| Emergency stop | Hold Escape for 2 seconds (always active, UI-independent) |
| Stop all macros | STOP ALL button in toolbar, or a configurable global hotkey |
| Per-slot controls | Bind custom Rec / Play / Stop keys per slot in the Hotkey Manager |
| Save workspace | Save Session in toolbar — choose Portable or Locked to this Mac |
| Restore workspace | Load Session in toolbar |

---

## Project Structure

```
sally-clicks/
├── main.py                # Entry point and OS signal handling
├── config.py              # UI theme, colours, and constants
├── recorder.py            # MacroEngine — Quartz recording and playback
├── input_handler.py       # CGEvent injection
├── requirements.txt
├── utils/
│   └── persistence.py     # Validation, checksum/HMAC, save and load
└── ui/
    ├── app.py             # Window chrome, slot management, session I/O
    ├── slot_card.py       # Per-macro card widget
    ├── stitch_dialog.py   # Drag-and-drop stitch UI
    ├── hotkey_manager.py  # Hotkey binding window
    ├── input_manager.py   # Global input listener and escape hatch
    ├── password_guard.py  # Accessibility secure field detection
    ├── security_dialog.py # Portable vs. locked session choice dialog
    ├── timeline.py        # Event timeline canvas
    └── widgets.py         # Shared UI primitives
```

---

## Licence

MIT — do whatever you want, just don't blame me if it clicks something you didn't expect.