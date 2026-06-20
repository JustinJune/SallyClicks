# input_handler.py 
# does not use Quartz CGEvents anymore
import sys
import os
import time
import ctypes
from utils import logger

'''
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
'''

BASE_DIR = os.path.dirname(os.path.abspath(__file__)) # Adjust if needed
if os.path.basename(BASE_DIR) == "ui":
    BASE_DIR = os.path.dirname(BASE_DIR)
DYLIB_PATH = os.path.join(BASE_DIR, "libsally.dylib")

try:
    sally_lib = ctypes.CDLL(DYLIB_PATH)
except OSError:
    print(f"[Error] Could not find {DYLIB_PATH}. Compile it first!", file=sys.stderr)
    sys.exit(1)
_held_keys:  set[str] = set()
_held_mouse: set[str] = set()

sally_lib.check_accessibility.restype = ctypes.c_bool
sally_lib.inject_mouse.argtypes = [ctypes.c_double, ctypes.c_double, ctypes.c_int32, ctypes.c_bool]
sally_lib.inject_key.argtypes = [ctypes.c_uint16, ctypes.c_bool]

KEY_CALLBACK = ctypes.CFUNCTYPE(None, ctypes.c_uint16, ctypes.c_bool)
MOUSE_CALLBACK = ctypes.CFUNCTYPE(None, ctypes.c_double, ctypes.c_double, ctypes.c_int32, ctypes.c_bool)
sally_lib.start_listener.argtypes = [KEY_CALLBACK, MOUSE_CALLBACK]

# Keep references to prevent garbage collection
_k_cb = None
_m_cb = None

_held_keys = set()
_held_mouse = set()

# --- Public API ---
def is_trusted() -> bool:
    return sally_lib.check_accessibility()

def start_native_listener(on_key, on_mouse):
    global _k_cb, _m_cb
    _k_cb = KEY_CALLBACK(on_key)
    _m_cb = MOUSE_CALLBACK(on_mouse)
    sally_lib.start_listener(_k_cb, _m_cb)

def stop_native_listener():
    sally_lib.stop_listener()

def _key_to_code(key_str: str) -> int | None:
    s = key_str.strip("'\"")
    if s.startswith("cg:"):
        try: return int(s[3:])
        except: return None
    return None

'''
# -- Old Internal helpers ---

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
'''

# -- Public API ---

def fire_event(event: dict) -> None:
    """
    Execute one input event synchronously.
    Timing/delays are the caller's responsibility (recorder.py handles them).
    Errors are swallowed so a bad event never kills the playback thread.
    """
    try:
        t   = event["type"]
        if t in ("click", "click_down", "click_up"):
            x, y = float(event["x"]), float(event["y"])
            btn_str = str(event.get("button", "Button.left"))
            if "right" in btn_str:
                bid = 1
            elif "middle" in btn_str:
                bid = 2
            else:
                bid = 0
            
            if t == "click":
                sally_lib.inject_mouse(x, y, bid, True)
                time.sleep(0.012)
                sally_lib.inject_mouse(x, y, bid, False)
            elif t == "click_down":
                sally_lib.inject_mouse(x, y, bid, True)
                _held_mouse.add(str(btn_str))
            elif t == "click_up":
                sally_lib.inject_mouse(x, y, bid, False)
                _held_mouse.discard(str(btn_str))

        elif t in ("key", "key_down", "key_up"):
            k = str(event.get("key", ""))
            code = _key_to_code(k)
            if code is None: return

            if t == "key":
                dur = max(float(event.get("duration", 0.05)), 0.012)
                sally_lib.inject_key(code, True)
                time.sleep(dur)
                sally_lib.inject_key(code, False)
            elif t == "key_down":
                sally_lib.inject_key(code, True)
                _held_keys.add(k)
            elif t == "key_up":
                sally_lib.inject_key(code, False)
                _held_keys.discard(k)
    except Exception as e:
        logger.error(f"Event failed: {e}")

# Release every key/button currently tracked as held. 
# Call on stop/crash.
def release_all() -> None:
    # Release all held keys
    for key in list(_held_keys):
        code = _key_to_code(key)
         # Skip keys that cannot be mapped to a virtual key code
        if code is None:
            continue

        sally_lib.inject_key(code, False)

    # Release all held mouse buttons.
    for button in list(_held_mouse):

        if "right" in button:
            button_id = 1
        elif "middle" in button:
            button_id = 2
        else:
            # Default to left mouse button.
            button_id = 0

        sally_lib.inject_mouse(
            0,        
            0,         
            button_id,
            False      
        )
        '''
        try:
            _post_key(k, False)
        except Exception as e:
            print(f"[Sally Clicks] Failed to release key {k!r}: {e}", file=sys.stderr)
            logger.error(f"Emergency release failed for key {k!r}: {e}")
    for b in list(_held_mouse):
        try:
            _, up, bid = _mouse_consts(b)
            _post_mouse(up, 0, 0, bid)
        except Exception as e:
            print(f"[Sally Clicks] Failed to release button {b!r}: {e}", file=sys.stderr)
            logger.error(f"Emergency release failed for mouse button {b!r}: {e}")
            '''
    # Clear tracking state
    _held_keys.clear()
    _held_mouse.clear()

# Legacy alias
execute_event = fire_event