# main.py — Sally Clicks! 
import platform
import signal
import sys
import tkinter as tk
from tkinter import messagebox

from ui.app import AppGUI
import input_handler   


# --- Signal handler: release all inputs on crash / SIGTERM / Ctrl-C ---

def _emergency_release(signum, frame):
    """
    Called by the OS on SIGTERM, SIGINT, or any registered signal.
    Runs outside the normal call stack — keep it minimal.
    """
    try:
        input_handler.release_all()
    except Exception:
        pass
    sys.exit(0)


signal.signal(signal.SIGTERM, _emergency_release)
signal.signal(signal.SIGINT,  _emergency_release)
# SIGHUP fires when the terminal is closed
if hasattr(signal, "SIGHUP"):
    signal.signal(signal.SIGHUP, _emergency_release)


# --- macOS helpers ---
# Ask macOS for high-priority execution so it won't throttle timers.
def _prevent_app_nap():
    if platform.system() == "Darwin":
        try:
            from Foundation import NSProcessInfo
            NSProcessInfo.processInfo().beginActivityWithOptions_reason_(
                0x00FFFFFF, "Macro Playback Active"
            )
        except ImportError:
            pass

# Warn if macOS Accessibility permission is missing.
def _check_accessibility(root: tk.Tk):
    if platform.system() != "Darwin":
        return
    import subprocess
    try:
        result = subprocess.run(
            ["osascript", "-e",
             'tell application "System Events" to return name of every process'],
            capture_output=True, timeout=2,
        )
        if result.returncode != 0:
            messagebox.showwarning(
                "Accessibility Permission Required",
                "Sally Clicks! needs Accessibility access to record and replay inputs.\n\n"
                "Go to:\n"
                "System Settings → Privacy & Security → Accessibility\n\n"
                "Add your Terminal (or Python) app and re-launch.",
                parent=root,
            )
    except Exception:
        pass


# Entry point 

if __name__ == "__main__":
    root = tk.Tk()
    _prevent_app_nap()
    _check_accessibility(root)
    app = AppGUI(root)
    root.mainloop()