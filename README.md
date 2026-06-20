# Sally Clicks!

A natively-injected macOS macro recorder with a clean multi-slot UI.

Record mouse clicks and keystrokes, save them, stitch them together, and replay
with absolute-time precision. This macro is built exclusively for macOS. 
---

## Features

### Precision Playback

- **Absolute-time scheduling** — zero drift, even on long or complex macros
- **True key holds** — records exactly how long each key was held and replays it faithfully
- **Speed scaling** — replay at 0.5×, 1×, 2×, 4×, or 8×
- **Loop control** — set a repeat count or loop infinitely with a live countdown
- **Autoclicker** — Dynamically clicks where your mouse is at a set interval

### Multi-Slot Workspace

- **8 independent slots** — run up to 8 distinct macros side by side in one window
- **Stitch** — drag and drop any combination of slots to chain them into a single macro
- **Session save / load** — save your entire workspace (all slots, hotkeys, and settings)
  and restore it in one click
- **Compact form** - Make your window even smaller by only keeping rec/play/stop features + macro name

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

Requires macOS 12 (Monterey) or later and Python 3.10+ and the Swift toolchain
(ships with Xcode or Xcode Command Line Tools).

```bash
git clone https://github.com/JustinJune/SallyClicks
cd SallyClicks
python -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
make build     
python main.py
```

**`make build` must be run before the first launch.** 

## Building a Standalone App (Optional)

If you prefer not to run the application from the terminal every time, you can compile into a native macOS `.app` bundle using PyInstaller. 

**1. Build the Swift engine first**
```bash
make build
```

**2. Install PyInstaller and bundle**
Ensure your virtual environment is activated, then run:
```bash
pip install pyinstaller
pyinstaller --windowed --noconfirm --name "Sally Clicks" \
  --add-binary "libsally.dylib:." \
  main.py
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

## Architecture: Python + Native Swift Bridge

Sally Clicks is split across two layers:

| Layer | Responsibility | Language |
|-------|----------------|----------|
| UI, scheduling, persistence, hotkeys | Window chrome, slot management, timing, save/load, validation | Python (Tkinter) |
| Input recording and injection | The actual `CGEventTap` listener and `CGEventPost` calls | Swift, compiled to `libsally.dylib` |

## Project Structure

```
sally-clicks/
├── main.py                # Entry point and OS signal handling
├── config.py              # UI theme, colours, and constants
├── sally_engine.swift     # Native Swift source — CGEventTap + CGEventPost
├── recorder.py            # MacroEngine — Quartz recording and playback
├── input_handler.py       # CGEvent injection
├── requirements.txt
├── libsally.dylib         # Compiled output of sally_engine.swift (build artifact, gitignored)
├── autoclicker.py         # Autoclicker logic
├── utils/
│   └── persistence.py     # Validation, checksum/HMAC, save and load
|   └── logger.py          # Keep a log when in app form
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
    └── autoclicker_window.py # Window UI
```

---

## Licence

MIT — do whatever you want, just don't blame me if it clicks something you didn't expect.