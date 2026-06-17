# input_handler.py — macOS only (Quartz CGEvents)
import sys
import time

import Quartz
from Quartz import (
    CGEventCreateMouseEvent, CGEventCreateKeyboardEvent,
    CGEventPost,
    kCGEventLeftMouseDown,  kCGEventLeftMouseUp,
    kCGEventRightMouseDown, kCGEventRightMouseUp,
    kCGEventOtherMouseDown, kCGEventOtherMouseUp,
    kCGMouseButtonLeft, kCGMouseButtonRight, kCGMouseButtonCenter,
    kCGHIDEventTap,
    kCGEventKeyDown, kCGEventKeyUp,  # noqa: F401 — imported for callers
)

# ── CGKeyCode table ───────────────────────────────────────────────────────────
_KEY_NAME_TO_CG: dict[str, int] = {
    "space": 49, "return": 36, "enter": 36, "tab": 48,
    "delete": 51, "backspace": 51, "escape": 53, "esc": 53,
    "up": 126, "down": 125, "left": 123, "right": 124,
    "home": 115, "end": 119, "page_up": 116, "page_down": 121,
    "f1": 122,  "f2": 120,  "f3": 99,   "f4": 118,
    "f5": 96,   "f6": 97,   "f7": 98,   "f8": 100,
    "f9": 101,  "f10": 109, "f11": 103, "f12": 111,
    "cmd": 55, "command": 55, "shift": 56,
    "alt": 58, "option": 58, "ctrl": 59, "control": 59,
    "caps_lock": 57,
    "a": 0,  "s": 1,  "d": 2,  "f": 3,  "h": 4,  "g": 5,
    "z": 6,  "x": 7,  "c": 8,  "v": 9,  "b": 11, "q": 12,
    "w": 13, "e": 14, "r": 15, "y": 16, "t": 17,
    "1": 18, "2": 19, "3": 20, "4": 21, "6": 22, "5": 23,
    "=": 24, "9": 25, "7": 26, "-": 27, "8": 28, "0": 29,
    "]": 30, "o": 31, "u": 32, "[": 33, "i": 34, "p": 35,
    "l": 37, "j": 38, "'": 39, "k": 40, ";": 41, "\\": 42,
    ",": 43, "/": 44, "n": 45, "m": 46, ".": 47, "`": 50,
}

_held_keys:  set[str] = set()
_held_mouse: set[str] = set()


# ── Internal helpers ──────────────────────────────────────────────────────────

def _mouse_consts(btn_str: str) -> tuple:
    """Return (event_down, event_up, button_id) for a button string."""
    s = str(btn_str)
    if "right"  in s: return kCGEventRightMouseDown, kCGEventRightMouseUp, kCGMouseButtonRight
    if "middle" in s: return kCGEventOtherMouseDown, kCGEventOtherMouseUp, kCGMouseButtonCenter
    return kCGEventLeftMouseDown, kCGEventLeftMouseUp, kCGMouseButtonLeft


def _post_mouse(event_type: int, x: int, y: int, button_id: int) -> None:
    pt = Quartz.CGPoint(x=x, y=y)
    ev = CGEventCreateMouseEvent(None, event_type, pt, button_id)
    if ev:
        CGEventPost(kCGHIDEventTap, ev)


def _key_to_code(key_str: str) -> int | None:
    s = key_str.strip("'\"")
    if s.startswith("cg:"):           # native Quartz keycode e.g. "cg:49"
        try:    return int(s[3:])
        except: return None
    if s.startswith("Key."):          # pynput name e.g. "Key.space"
        return _KEY_NAME_TO_CG.get(s[4:].lower())
    if len(s) == 1:                   # single character e.g. "a"
        return _KEY_NAME_TO_CG.get(s.lower())
    return _KEY_NAME_TO_CG.get(s.lower())


def _post_key(key_str: str, down: bool) -> None:
    code = _key_to_code(str(key_str))
    if code is None:
        return
    ev = CGEventCreateKeyboardEvent(None, code, down)
    if ev:
        CGEventPost(kCGHIDEventTap, ev)


# ── Public API ────────────────────────────────────────────────────────────────

def fire_event(event: dict) -> None:
    """
    Execute one input event synchronously.
    Timing/delays are the caller's responsibility (recorder.py handles them).
    Errors are swallowed so a bad event never kills the playback thread.
    """
    try:
        t   = event["type"]
        btn = event.get("button", "Button.left")

        if t in ("click", "click_down", "click_up"):
            x, y          = int(event["x"]), int(event["y"])
            dn, up, bid   = _mouse_consts(str(btn))

            if t == "click":
                _post_mouse(dn, x, y, bid)
                time.sleep(0.012)
                _post_mouse(up, x, y, bid)
            elif t == "click_down":
                _post_mouse(dn, x, y, bid)
                _held_mouse.add(str(btn))
            elif t == "click_up":
                _post_mouse(up, x, y, bid)
                _held_mouse.discard(str(btn))

        elif t in ("key", "key_down", "key_up"):
            k = str(event.get("key", ""))

            if t == "key":
                dur = max(float(event.get("duration", 0.05)), 0.012)
                _post_key(k, True)
                time.sleep(dur)
                _post_key(k, False)
            elif t == "key_down":
                _post_key(k, True)
                _held_keys.add(k)
            elif t == "key_up":
                _post_key(k, False)
                _held_keys.discard(k)

    except Exception:
        pass


def release_all() -> None:
    """Release every key/button currently tracked as held. Call on stop/crash."""
    for k in list(_held_keys):
        try:
            _post_key(k, False)
        except Exception as e:
            print(f"[Sally Clicks] Failed to release key {k!r}: {e}", file=sys.stderr)
    for b in list(_held_mouse):
        try:
            _, up, bid = _mouse_consts(b)
            _post_mouse(up, 0, 0, bid)
        except Exception as e:
            print(f"[Sally Clicks] Failed to release button {b!r}: {e}", file=sys.stderr)
    _held_keys.clear()
    _held_mouse.clear()


# Legacy alias
execute_event = fire_event