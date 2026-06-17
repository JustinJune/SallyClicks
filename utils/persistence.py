# utils/persistence.py
#
# File format (saved by Sally Clicks):
#   {
#     "events": [ ... ],
#     "hmac":   "<hex digest>"
#   }
#
# The HMAC is SHA-256 keyed with a machine-specific secret derived from the
# macOS hardware UUID. This means:
#   - Files you save on your machine load fine
#   - A file someone else crafted (or hand-edited) will fail the HMAC check
#     and be refused, preventing tampered macros from running
#
import hashlib
import hmac as _hmac
import json
import os
import subprocess
import sys
import tkinter as tk
import base64
from cryptography.fernet import Fernet

# ── Machine-bound HMAC key ────────────────────────────────────────────────────

def _machine_key() -> bytes:
    """
    Derive a stable, machine-specific 32-byte key from the macOS hardware UUID.
    Falls back to a fixed salt if the UUID can't be read (shouldn't happen on macOS).
    """
    try:
        result = subprocess.run(
            ["ioreg", "-rd1", "-c", "IOPlatformExpertDevice"],
            capture_output=True, text=True, timeout=3,
        )
        for line in result.stdout.splitlines():
            if "IOPlatformUUID" in line:
                uuid = line.split('"')[-2]
                return hashlib.sha256(f"sally-clicks:{uuid}".encode()).digest()
    except Exception:
        pass
    # Fallback — still better than nothing
    return hashlib.sha256(b"sally-clicks:fallback-key-mac").digest()


_KEY = _machine_key()
_FERNET_KEY = base64.urlsafe_b64encode(_KEY)
_cipher = Fernet(_FERNET_KEY)

def _compute_hmac(events_json: str) -> str:
    return _hmac.new(_KEY, events_json.encode("utf-8"), hashlib.sha256).hexdigest()


def _compute_hmac(events_json: str) -> str:
    return _hmac.new(_KEY, events_json.encode("utf-8"), hashlib.sha256).hexdigest()


# ── Screen bounds ─────────────────────────────────────────────────────────────

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

# ── Security constants ────────────────────────────────────────────────────────

VALID_TYPES   = {"click", "click_down", "click_up", "key", "key_down", "key_up"}
VALID_BUTTONS = {"Button.left", "Button.right", "Button.middle"}
MAX_DELAY     = 300.0  # seconds
MAX_DURATION  = 60.0   # seconds

# Keys that warrant a warning when found in an *imported* (external) macro
MODIFIER_KEYS = {"cmd", "command", "ctrl", "control", "cg:55", "cg:59"}


# ── Validation ────────────────────────────────────────────────────────────────

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


def contains_modifier_keys(events: list[dict]) -> bool:
    """Return True if any event uses a system modifier key."""
    for ev in events:
        key = str(ev.get("key", "")).lower()
        if key in MODIFIER_KEYS:
            return True
    return False


# ── Serialise ─────────────────────────────────────────────────────────────────

def serialize_events(events: list) -> list:
    clean = []
    for event in events:
        ev = event.copy()
        t  = ev.get("type", "")

        if t in ("click", "click_down", "click_up"):
            ev["button"] = str(ev.get("button", "Button.left"))
        elif t in ("key", "key_down", "key_up"):
            key = ev.get("key", "")
            if not isinstance(key, str):
                if hasattr(key, "name") and key.name:
                    ev["key"] = f"Key.{key.name}"
                elif hasattr(key, "char") and key.char:
                    ev["key"] = key.char
                else:
                    ev["key"] = str(key)

        ev.setdefault("delay", 0)
        clean.append(ev)
    return clean


# ── Public API ────────────────────────────────────────────────────────────────

def save_macro(filename: str, events: list) -> bool:
    """Save events to a signed JSON file. Returns True on success."""
    try:
        serialized  = serialize_events(events)
        events_json = json.dumps(serialized, indent=4)
        payload = {
            "events": serialized,
            "hmac":   _compute_hmac(events_json),
        }
        with open(filename, "w") as f:
            json.dump(payload, f, indent=4)
        return True
    except Exception as e:
        print(f"Save error: {e}", file=sys.stderr)
        return False


def load_macro(filename: str) -> tuple[list, str | None]:
    """
    Load and verify a macro file.

    Returns (events, None) on success.
    Returns ([], error_string) on any failure — caller shows this to the user.
    """
    if not os.path.exists(filename):
        return [], f"File not found: {filename}"

    try:
        with open(filename, "r") as f:
            payload = json.load(f)
    except json.JSONDecodeError as e:
        return [], f"Invalid JSON: {e}"
    except Exception as e:
        return [], f"Could not read file: {e}"

    # ── Detect format ─────────────────────────────────────────────────────────
    if isinstance(payload, list):
        raw_events = payload
        hmac_status = "legacy"
    elif isinstance(payload, dict) and "events" in payload:
        raw_events   = payload["events"]
        stored_hmac  = payload.get("hmac", "")

        events_json    = json.dumps(raw_events, indent=4)
        expected_hmac  = _compute_hmac(events_json)

        if not stored_hmac:
            hmac_status = "missing"
        elif not _hmac.compare_digest(stored_hmac, expected_hmac):
            return [], (
                "Security check failed: this file has been modified outside of "
                "Sally Clicks and cannot be loaded.\n\n"
                "If you edited it intentionally, re-save it from within the app."
            )
        else:
            hmac_status = "ok"
    else:
        return [], "Unrecognised file format."

    # ── Validate events ───────────────────────────────────────────────────────
    try:
        events = validate_events(raw_events)
    except ValidationError as e:
        return [], str(e)

    if hmac_status == "legacy":
        for ev in events:
            ev["_legacy_file"] = True

    return events, None


# ── Global Workspace API ──────────────────────────────────────────────────────

def save_session(filename: str, session_data: dict, is_secure: bool = False) -> bool:
    """Save the entire workspace state (multiple slots + hotkeys) to a signed JSON file.
    If is_secure is True, the entire session is heavily encrypted."""
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

        session_json = json.dumps(clean_session, indent=4)
        
        if is_secure:
            # Encrypt the raw JSON string
            payload_data = _cipher.encrypt(session_json.encode("utf-8")).decode("utf-8")
        else:
            # Keep as plain dict for portability
            payload_data = clean_session

        # Wrap it with our HMAC signature to prevent tampering
        payload = {
            "version": 2,
            "is_locked": is_secure,
            "session_data": payload_data,
            "hmac": _compute_hmac(session_json),
        }
        
        with open(filename, "w") as f:
            json.dump(payload, f, indent=4)
        return True
        
    except Exception as e:
        print(f"Save session error: {e}", file=sys.stderr)
        return False


def load_session(filename: str) -> tuple[dict | None, str | None]:
    """Load, decrypt (if needed), and verify a full workspace session file."""
    if not os.path.exists(filename):
        return None, f"File not found: {filename}"

    try:
        with open(filename, "r") as f:
            payload = json.load(f)
    except json.JSONDecodeError as e:
        return None, f"Invalid JSON: {e}"
    except Exception as e:
        return None, f"Could not read file: {e}"

    if not isinstance(payload, dict) or "session_data" not in payload:
        return None, "Unrecognised file format. This is not a valid Sally Clicks session."

    is_locked   = payload.get("is_locked", False)
    stored_hmac = payload.get("hmac", "")

    # 1. Decrypt if locked
    try:
        if is_locked:
            decrypted_bytes = _cipher.decrypt(payload["session_data"].encode("utf-8"))
            session_json = decrypted_bytes.decode("utf-8")
            raw_session = json.loads(session_json)
        else:
            raw_session = payload["session_data"]
            session_json = json.dumps(raw_session, indent=4)
    except Exception:
        return None, "Decryption failed. This session is securely locked to a different Mac."

    # 2. Verify Integrity
    expected_hmac = _compute_hmac(session_json)
    if not stored_hmac or not _hmac.compare_digest(stored_hmac, expected_hmac):
        return None, "Integrity check failed: this session file has been altered."

    # 3. Validate Events for every slot
    try:
        for s in raw_session.get("slots", []):
            s["events"] = validate_events(s.get("events", []))
    except ValidationError as e:
        return None, f"Corrupt event data inside session: {e}"

    return raw_session, None