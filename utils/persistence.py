# utils/persistence.py
#
# Two file types:
#   Individual macro  (.json) — portable, app-level SHA-256 checksum
#   Session workspace (.json) — portable (checksum) OR machine-locked (Fernet AES)
# Portability choice:
#   Individual macros are always portable — checksum uses a fixed app salt.
#   Sessions can be saved as portable OR machine-locked (user's choice via
#   the security_dialog). Machine-locked sessions are Fernet-encrypted with a
#   key derived from the Mac's hardware UUID and cannot be opened on another machine.
import hashlib
import hmac as _hmac
import json
import os
import subprocess
import sys
import tkinter as tk
import base64
from cryptography.fernet import Fernet
from dataclasses import dataclass

# --- App level key for individual macros ---
# Not really for security, just a check to see if it was tampered with
# after saving it from the app itself
_PORTABLE_SALT = "sally-clicks-v1:"

# --- Machine-bound HMAC key ---
def _machine_key() -> bytes:
    try:
        result = subprocess.run(
            ["ioreg", "-rd1", "-c", "IOPlatformExpertDevice"],
            capture_output=True, text=True, timeout=3,
        )
        for line in result.stdout.splitlines():
            if "IOPlatformUUID" in line:
                uuid = line.split('"')[-2]
                return hashlib.sha256(f"sally-clicks:{uuid}".encode()).digest()
    except Exception as e:
        print(f"[Sally Clicks] Could not read hardware UUID: {e}", file=sys.stderr)
    # Fallback — better than nothing
    return hashlib.sha256(b"sally-clicks:fallback-key-mac").digest()


_MACHINE_KEY = _machine_key()
_FERNET_KEY = base64.urlsafe_b64encode(_MACHINE_KEY)
_cipher = Fernet(_FERNET_KEY)

# --- HMAC for locked sessions___
def _compute_hmac(events_json: str) -> str:
    return _hmac.new(_MACHINE_KEY, events_json.encode("utf-8"), hashlib.sha256).hexdigest()

# --- Checksum for portability ---
def _canonical_json(obj) -> str:
    return json.dumps(obj, separators=(",", ":"), sort_keys=True)

def _checksum(json_str: str) -> str:
    return hashlib.sha256((_PORTABLE_SALT + json_str).encode()).hexdigest()

# --- Screen bounds ---

def _screen_size() -> tuple[int, int]:
    try:
        r = tk.Tk()
        r.withdraw()
        w, h = r.winfo_screenwidth(), r.winfo_screenheight()
        r.destroy()
        return w, h
    except Exception:
        return 7680, 4320  # 8K upper bound

_SCREEN_W, _SCREEN_H = _screen_size()

# --- Security constants ---

VALID_TYPES   = {"click", "click_down", "click_up", "key", "key_down", "key_up"}
VALID_BUTTONS = {"Button.left", "Button.right", "Button.middle"}
MAX_DELAY     = 300.0  # seconds
MAX_DURATION  = 60.0   # seconds

# Keys that warrant a warning when found in an *imported* (external) macro
MODIFIER_KEYS = {"cmd", "command", "ctrl", "control", "cg:55", "cg:59"}

# --- Load result dataclass
@dataclass
class LoadResult:
    events:        list
    error:         str | None = None
    is_legacy:     bool       = False
    has_modifiers: bool       = False

# --- Validation ---

class ValidationError(Exception):
    pass


def _validate_event(ev: dict, idx: int) -> dict:
    if not isinstance(ev, dict):
        raise ValidationError(f"Event {idx}: expected a dict, got {type(ev).__name__}")

    t = ev.get("type")
    if t not in VALID_TYPES:
        raise ValidationError(f"Event {idx}: unknown type {t!r}")

    clean = {"type": t}

    raw_delay = ev.get("delay", 0)
    if not isinstance(raw_delay, (int, float)):
        raise ValidationError(f"Event {idx}: 'delay' must be a number")
    delay = float(raw_delay)
    if not (0 <= delay <= MAX_DELAY):
        raise ValidationError(f"Event {idx}: delay {delay:.3f}s out of range [0, {MAX_DELAY}]")
    clean["delay"] = delay

    if t in ("click", "click_down", "click_up"):
        for coord, limit in (("x", _SCREEN_W), ("y", _SCREEN_H)):
            raw = ev.get(coord)
            if not isinstance(raw, (int, float)):
                raise ValidationError(f"Event {idx}: '{coord}' must be a number")
            v = float(raw)
            if not (-limit <= v <= limit * 2):
                raise ValidationError(
                    f"Event {idx}: {coord}={v} is outside screen bounds"
                )
            clean[coord] = v

        btn = str(ev.get("button", "Button.left"))
        if btn not in VALID_BUTTONS:
            btn = ("Button.right" if "right" in btn
                   else "Button.middle" if "middle" in btn
                   else "Button.left")
        clean["button"] = btn

    elif t in ("key", "key_down", "key_up"):
        key = ev.get("key")
        if not isinstance(key, str):
            raise ValidationError(f"Event {idx}: 'key' must be a string")
        if len(key) > 32:
            raise ValidationError(f"Event {idx}: 'key' is suspiciously long")
        clean["key"] = key

        if t == "key":
            raw_dur = ev.get("duration", 0.05)
            if not isinstance(raw_dur, (int, float)):
                raise ValidationError(f"Event {idx}: 'duration' must be a number")
            dur = float(raw_dur)
            if not (0 <= dur <= MAX_DURATION):
                raise ValidationError(f"Event {idx}: duration {dur:.3f}s out of range")
            clean["duration"] = dur

    return clean


def validate_events(events) -> list[dict]:
    if not isinstance(events, list):
        raise ValidationError(f"Expected a list, got {type(events).__name__}")
    return [_validate_event(ev, i) for i, ev in enumerate(events)]

# Return True if any event uses a system modifier key
def contains_modifier_keys(events: list[dict]) -> bool:
    for ev in events:
        key = str(ev.get("key", "")).lower()
        if key in MODIFIER_KEYS:
            return True
    return False


# --- Convert recorded events into JSON safe format ---

def serialize_events(events: list) -> list:
    clean = []
    # Process individual events and create copy to work on
    for event in events:
        ev = event.copy()
        t  = ev.get("type", "")
        # Convert button objects to strings
        if t in ("click", "click_down", "click_up"):
            ev["button"] = str(ev.get("button", "Button.left"))
        # Convert key objects to strings
        elif t in ("key", "key_down", "key_up"):
            key = ev.get("key", "")
            # if not string do not convert
            if not isinstance(key, str):
                # Special keys (enter, esc, etc..)
                if hasattr(key, "name") and key.name:
                    ev["key"] = f"Key.{key.name}"
                # Character keys (a, b, 1, 2...)
                elif hasattr(key, "char") and key.char:
                    ev["key"] = key.char
                else:
                    ev["key"] = str(key)

        ev.setdefault("delay", 0)
        clean.append(ev)
    return clean


# --- Save events to a signed JSON file. Returns True on success ---
# is_secure=True  → Fernet-encrypted, machine-locked, HMAC-signed
# is_secure=False → plain JSON, portable, checksum-signed
def save_macro(filename: str, events: list, is_secure: bool =False) -> bool:
    try:
        serialized  = serialize_events(events)
        events_json = _canonical_json(serialized)

        if is_secure:
            events_data_field = _cipher.encrypt(events_json.encode()).decode()
            sig = _compute_hmac(events_json) # HMAC with machine key
        else:
            events_data_field = serialized
            sig = _checksum(events_json)  # portable checksum

        payload = {
            "version": 2,
            "is_locked": is_secure,
            "events": events_data_field,
            "sig": sig,
        }
        with open(filename, "w") as f:
            json.dump(payload, f, indent=4)
        return True
    except Exception as e:
        print(f"Save error: {e}", file=sys.stderr)
        return False

# --- Load and verify macro file ---
# Return (events, None) on success
# Return ([], error_string) on any failure])
# Caller shows error to user
def load_macro(filename: str) -> LoadResult:
    if not os.path.exists(filename):
       return LoadResult(events=[], error=f"File not found: {filename}")

    try:
        with open(filename, "r") as f:
            payload = json.load(f)
    
    except json.JSONDecodeError as e:
        return LoadResult(events=[], error=f"Invalid JSON: {e}")
    except Exception as e:
        return LoadResult(events=[], error=f"Could not read file: {e}")
    is_legacy = False

    # --- Detect format ---
    if isinstance(payload, list):
        raw_events = payload
        is_legacy = True

    elif isinstance(payload, dict) and "events" in payload:
        is_locked  = payload.get("is_locked", False)
        stored_sig = payload.get("sig", payload.get("checksum", ""))


        if not stored_sig:
            is_legacy = True
            raw_events = payload["events"]
        else:
            try: 
                if is_locked:
                    decrypted    = _cipher.decrypt(payload["events"].encode())
                    events_json  = decrypted.decode()
                    raw_events   = json.loads(events_json)
                else:
                    raw_events   = payload["events"]
                    events_json  = _canonical_json(raw_events)
            except Exception:
                return LoadResult(events=[], error="Decryption failed. This macro is securely locked to a different Mac.")

            expected_sig = _compute_hmac(events_json) if is_locked else _checksum(events_json)
            if not stored_sig or stored_sig != expected_sig:
                return LoadResult(events=[], error="Integrity check failed: this file has been modified.")
    else:
        return LoadResult(events=[], error="Unrecognised file format.")

    try:
        events = validate_events(raw_events)
    except ValidationError as e:
        return LoadResult(events=[], error=str(e))

    return LoadResult(events=events, is_legacy=is_legacy, has_modifiers=contains_modifier_keys(events))

# --- Session save/load ---
# Save the entire workspace state (multiple slots + hotkeys) to a signed JSON file.
# If is_secure is True, the entire session is heavily encrypted.
def save_session(filename: str, session_data: dict, is_secure: bool = False) -> bool:
    try:
        # Clean and serialize the events inside every slot
        clean_session = {
            "type": "sally_session",
            "version": 2,
            "global_stop": session_data.get("global_stop", []),
            "slots": []
        }
        
        for s in session_data.get("slots", []):
            clean_slot = s.copy()
            clean_slot["events"] = serialize_events(s.get("events", []))
            clean_session["slots"].append(clean_slot)

        session_json = _canonical_json(clean_session)
        
        if is_secure:
            # Encrypt the raw JSON string
            session_data_field = _cipher.encrypt(session_json.encode()).decode()
            sig = _compute_hmac(session_json)     
        else:
            # Keep as plain dict for portability
            session_data_field = clean_session
            sig = _checksum(session_json) 

        # Wrap it with our HMAC signature to prevent tampering
        payload = {
            "version": 2,
            "is_locked": is_secure,
            "session_data": session_data_field,
            "sig": sig,
        }
        
        with open(filename, "w") as f:
            json.dump(payload, f, indent=4)
        return True
        
    except Exception as e:
        print(f"Save session error: {e}", file=sys.stderr)
        return False

#  Load, decrypt (if needed), and verify a full workspace session file.
def load_session(filename: str) -> tuple[dict | None, str | None]:
    if not os.path.exists(filename):
        return None, f"File not found: {filename}"

    try:
        with open(filename, "r") as f:
            payload = json.load(f)

    except Exception as e:
        return None, f"Could not read file: {e}"

    if not isinstance(payload, dict) or "session_data" not in payload:
        return None, "Unrecognised file format. This is not a valid Sally Clicks session."

    is_locked   = payload.get("is_locked", False)
    stored_sig = payload.get("sig", "")

    # Decrypt or extract
    try:
        if is_locked:
            decrypted = _cipher.decrypt(payload["session_data"].encode("utf-8"))
            session_json = decrypted.decode("utf-8")
            raw_session = json.loads(session_json)
        else:
            raw_session = payload["session_data"]
            session_json = _canonical_json(raw_session)
    except Exception:
        return None, "Decryption failed. This session is securely locked to a different Mac and cannot be opened."

    # Verify Integrity
    expected_sig = _compute_hmac(session_json) if is_locked else _checksum(session_json)
    if not stored_sig or stored_sig != expected_sig:
        return None, "Integrity check failed: this session file has been altered."

    # Validate Events for every slot
    try:
        for s in raw_session.get("slots", []):
            s["events"] = validate_events(s.get("events", []))
    except ValidationError as e:
        return None, f"Corrupt event data inside session: {e}"

    return raw_session, None