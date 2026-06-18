# ui/input_manager.py
# Single pynput listener pair that:
# routes key/mouse events to whichever SlotCard is currently recording
# fires hotkey checks on the main thread via root.after()
# handles key-binding capture mode
#. monitors Escape hold for emergency kill (UI-thread-independent)

import time
import threading
from pynput import mouse, keyboard
import input_handler  # for release_all()

# --- Escape-hatch constants ---
# Hold Escape for this many seconds to trigger an emergency stop.
# Runs entirely in the listener thread 
_ESCAPE_HOLD_SECS = 2.0


class GlobalInputManager:

    def __init__(self, app):
        self.app                = app
        self.held_keys          = set()
        self.binding_action     = None
        self.active_bind_btn    = None
        self.current_bind_combo = set()

        # Escape-hatch state (tracked in the listener thread)
        self._esc_press_time: float | None = None
        self._esc_timer: threading.Timer | None = None

        self.k_listener = keyboard.Listener(
            on_press=self.on_press, on_release=self.on_release,
        )
        self.m_listener = mouse.Listener(on_click=self.on_click)
        self.k_listener.start()
        self.m_listener.start()

    # --- Helpers ---

    def _key_str(self, key) -> str:
        if hasattr(key, "char") and key.char:
            return key.char.lower()
        if hasattr(key, "name"):
            return key.name.lower()
        return str(key).strip("'\"").lower()

    def _is_escape(self, k: str) -> bool:
        return k in ("esc", "escape")

    # --- Emergency kill ---
    #  runs in listener thread, no UI dependency

    def _arm_escape_hatch(self):
        """Start the 2-second hold timer for Escape."""
        self._esc_press_time = time.monotonic()
        self._esc_timer = threading.Timer(_ESCAPE_HOLD_SECS, self._fire_escape_hatch)
        self._esc_timer.daemon = True
        self._esc_timer.start()

    def _disarm_escape_hatch(self):
        """Cancel the timer if Escape is released early."""
        if self._esc_timer:
            self._esc_timer.cancel()
            self._esc_timer = None
        self._esc_press_time = None

    def _fire_escape_hatch(self):
        """
        Called after Escape has been held for _ESCAPE_HOLD_SECS.
        Runs in a Timer thread — safe to call release_all() directly,
        and schedules a UI reset via after() for anything UI-related.
        """
        # Release all physical inputs immediately 
        input_handler.release_all()

        # Stop every engine's playback flag 
        for slot in self.app.slots:
            try:
                slot.engine.is_playing  = False
                slot.engine.is_recording = False
            except Exception:
                pass

        # Ask the UI thread to reset button states
        try:
            self.app.root.after(0, self._ui_reset_after_escape)
        except Exception:
            pass

    def _ui_reset_after_escape(self):
        """UI-thread cleanup after escape hatch fires."""
        for slot in self.app.slots:
            try:
                slot._reset_btns()
                slot._set_status("⚠ Emergency stop", "#B45309")
            except Exception:
                pass

    # --- Key events ---

    def on_press(self, key):
        k = self._key_str(key)
        self.held_keys.add(k)

        # Escape hatch: arm on first press 
        if self._is_escape(k) and self._esc_press_time is None:
            self._arm_escape_hatch()

        # Binding capture mode
        if self.binding_action:
            if self._is_escape(k):
                original = getattr(self, "original_combo", frozenset())
                self.app.root.after(
                    0, self.app.finish_binding, self.binding_action, original
                )
                self.binding_action     = None
                self.current_bind_combo = set()
                self.held_keys.clear()
                return
            
            if k in ("backspace", "delete"):
                self.app.root.after(
                    0, self.app.finish_binding, self.binding_action, frozenset()
                )
                self.binding_action     = None
                self.current_bind_combo = set()
                self.held_keys.clear()
                return

            self.current_bind_combo.add(k)
            combo_str = " + ".join(sorted(self.current_bind_combo))
            self.app.root.after(
                0, self.app.update_bind_ui,
                self.binding_action[0], self.binding_action[1], combo_str,
            )
            return

        # Normal hotkey check
        self.app.root.after(0, self.app.check_hotkeys, frozenset(self.held_keys))

        # Forward to recording engines
        for slot in self.app.slots:
            if slot.engine.is_recording:
                slot.engine.on_press(key)

    def on_release(self, key):
        k = self._key_str(key)

        # Disarm escape hatch on release (only if it hasn't already fired)
        if self._is_escape(k):
            self._disarm_escape_hatch()

        if self.binding_action:
            if self.current_bind_combo:
                frozen = frozenset(self.current_bind_combo)
                self.app.root.after(
                    0, self.app.finish_binding, self.binding_action, frozen,
                )
                self.binding_action     = None
                self.current_bind_combo = set()
                self.held_keys.clear()
            return

        self.held_keys.discard(k)

        for slot in self.app.slots:
            if slot.engine.is_recording:
                slot.engine.on_release(key)

    def on_click(self, x, y, button, pressed):
        if self.binding_action:
            return
        for slot in self.app.slots:
            if slot.engine.is_recording:
                slot.engine.on_click(x, y, button, pressed)

    #  Explicitly kill the pynput listeners 
    def shutdown(self):
        try:
            self.k_listener.stop()
            self.m_listener.stop()
            if self._esc_timer:
                self._esc_timer.cancel()
        except Exception:
            pass