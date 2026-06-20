# ui/input_manager.py
# Single pynput listener pair that:
# routes key/mouse events to whichever SlotCard is currently recording
# fires hotkey checks on the main thread via root.after()
# handles key-binding capture mode
#. monitors Escape hold for emergency kill (UI-thread-independent)

import time
import threading
import input_handler  # for release_all()
from utils import logger

# --- Escape-hatch constants ---
# Hold Escape for this many seconds to trigger an emergency stop.
# Runs entirely in the listener thread 
_ESCAPE_HOLD_SECS = 2.0

MAC_KEYCODES = {
    53: "escape", 51: "backspace", 117: "delete", 36: "return", 49: "space",
    59: "control", 58: "option", 55: "command", 56: "shift",
    0: "a", 1: "s", 2: "d", 3: "f", 4: "h", 5: "g", 6: "z", 7: "x", 8: "c", 9: "v",
    11: "b", 12: "q", 13: "w", 14: "e", 15: "r", 16: "y", 17: "t", 31: "o", 32: "u",
    34: "i", 35: "p", 37: "l", 38: "j", 39: "'", 40: "k", 41: ";", 42: "\\", 43: ",",
    44: "/", 45: "n", 46: "m", 47: ".",
    18: "1", 19: "2", 20: "3", 21: "4", 22: "6", 23: "5", 25: "9", 26: "7", 28: "8", 29: "0"
}

class GlobalInputManager:

    def __init__(self, app):
        self.app = app
        self.held_keys = set()
        self.binding_action = None
        self.active_bind_btn = None
        self.current_bind_combo = set()

        # Escape-hatch state 
        self._esc_press_time = None
        self._esc_timer= None

        self._listener_thread = threading.Thread(target=self._run_listener, daemon=True)
        self._listener_thread.start()

    # --- Helpers ---
    def _run_listener(self):
        input_handler.start_native_listener(
            self._native_on_key, 
            self._native_on_mouse
        )
    
    def shutdown(self):
        try:
            input_handler.stop_native_listener()
        except Exception as e:
            logger.error(f"Failed to stop native listener: {e}")
            
        # Safely check for the timer, even if it was never created
        if getattr(self, '_esc_timer', None):
            self._esc_timer.cancel()

    def _is_escape(self, k: str) -> bool:
        return k in ("esc", "escape")

    # --- Emergency kill ---
    #  runs in listener thread, no UI dependency

    # Start the 2 second hold timer for Escape
    def _arm_escape_hatch(self):
        self._esc_press_time = time.monotonic()
        self._esc_timer = threading.Timer(_ESCAPE_HOLD_SECS, self._fire_escape_hatch)
        self._esc_timer.daemon = True
        self._esc_timer.start()

    # Cancel the timer if Escape is released early
    def _disarm_escape_hatch(self):
        if self._esc_timer:
            self._esc_timer.cancel()
            self._esc_timer = None
        self._esc_press_time = None

        
    # Called after Escape has been held for _ESCAPE_HOLD_SECS.
    # Runs in a Timer thread — safe to call release_all() directly,
    # and schedules a UI reset via after() for anything UI-related.
    def _fire_escape_hatch(self):
        # Release all physical inputs immediately 
        input_handler.release_all()

        # Stop every engine's playback flag 
        for slot in self.app.slots:
            try:
                slot.engine.is_playing  = False
                slot.engine.is_recording = False
            except Exception as e:
                logger.error(f"Failed to stop playback on a slot during emergency: {e}", exc_info=True)

        # Ask the UI thread to reset button states
        try:
            self.app.root.after(0, self._ui_reset_after_escape)
        except Exception as e:
            logger.error(f"Failed to schedule UI reset after escape: {e}", exc_info=True)

    # UI-thread cleanup after escape hatch fires
    def _ui_reset_after_escape(self):
        for slot in self.app.slots:
            try:
                slot._reset_btns()
                slot._set_status("⚠ Emergency stop", "#B45309")
            except Exception as e:
                logger.error(f"Failed to cleanup ui threads: {e}", exc_info=True)

    def _native_on_key(self, keycode: int, is_down: bool):
        k_ui = MAC_KEYCODES.get(keycode, f"key_{keycode}")
        k_raw = f"cg:{keycode}" # The format your JSON files expect

        if is_down:
            self.held_keys.add(k_ui)
            if self._is_escape(k_ui) and self._esc_press_time is None:
                self._arm_escape_hatch()

            if self.binding_action:
                if self._is_escape(k_ui):
                    original = getattr(self, "original_combo", frozenset())
                    self.app.root.after(0, self.app.finish_binding, self.binding_action, original)
                    self.binding_action = None; self.current_bind_combo.clear(); self.held_keys.clear()
                    return
                if k_ui in ("backspace", "delete"):
                    self.app.root.after(0, self.app.finish_binding, self.binding_action, frozenset())
                    self.binding_action = None; self.current_bind_combo.clear(); self.held_keys.clear()
                    return

                self.current_bind_combo.add(k_ui)
                combo_str = " + ".join(sorted(self.current_bind_combo))
                self.app.root.after(0, self.app.update_bind_ui, self.binding_action[0], self.binding_action[1], combo_str)
                return

            self.app.root.after(0, self.app.check_hotkeys, frozenset(self.held_keys))

            # Pass the raw CG code to the recorder
            for slot in self.app.slots:
                if slot.engine.is_recording:
                    slot.engine.record_key("key_down", k_raw)
        else:
            if self._is_escape(k_ui): self._disarm_escape_hatch()
            if self.binding_action:
                if self.current_bind_combo:
                    frozen = frozenset(self.current_bind_combo)
                    self.app.root.after(0, self.app.finish_binding, self.binding_action, frozen)
                    self.binding_action = None; self.current_bind_combo.clear(); self.held_keys.clear()
                return

            self.held_keys.discard(k_ui)
            for slot in self.app.slots:
                if slot.engine.is_recording:
                    slot.engine.record_key("key_up", k_raw)

    def _native_on_mouse(self, x: float, y: float, button_id: int, is_down: bool):
        if self.binding_action: return
        btn_s = "Button.left" if button_id == 0 else "Button.right" if button_id == 1 else "Button.middle"
        t = "click_down" if is_down else "click_up"
        
        for slot in self.app.slots:
            if slot.engine.is_recording:
                slot.engine.record_mouse(t, x, y, btn_s)

    '''
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

    '''