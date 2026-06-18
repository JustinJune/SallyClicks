# recorder.py — macOS only (Quartz CGEvent tap)
import sys
import time
import threading
import input_handler
from utils.logger import logger

MIN_DELAY = 0.001  # 1 ms minimum between events — prevents injection storms

import Quartz
from Quartz import (
    CGEventTapCreate, CGEventTapEnable,
    CFMachPortCreateRunLoopSource, CFRunLoopAddSource,
    CFRunLoopGetCurrent, CFRunLoopRun, CFRunLoopStop,
    kCGSessionEventTap, kCGHeadInsertEventTap,
    kCGEventTapOptionDefault,
    kCGEventKeyDown, kCGEventKeyUp,
    kCGEventLeftMouseDown,  kCGEventLeftMouseUp,
    kCGEventRightMouseDown, kCGEventRightMouseUp,
    kCGEventOtherMouseDown, kCGEventOtherMouseUp,
    CGEventGetLocation, CGEventGetIntegerValueField,
    kCGKeyboardEventKeycode, kCGMouseEventButtonNumber,
    kCFRunLoopDefaultMode,
)

_MOUSE_DOWN = frozenset({
    kCGEventLeftMouseDown, kCGEventRightMouseDown, kCGEventOtherMouseDown,
})
_MOUSE_UP = frozenset({
    kCGEventLeftMouseUp, kCGEventRightMouseUp, kCGEventOtherMouseUp,
})
_MOUSE_MASK = (
    (1 << kCGEventKeyDown)        |
    (1 << kCGEventKeyUp)          |
    (1 << kCGEventLeftMouseDown)  |
    (1 << kCGEventLeftMouseUp)    |
    (1 << kCGEventRightMouseDown) |
    (1 << kCGEventRightMouseUp)   |
    (1 << kCGEventOtherMouseDown) |
    (1 << kCGEventOtherMouseUp)
)


class MacroEngine:
    def __init__(self):
        self.events       = []
        self.is_recording = False
        self.is_playing   = False
        self.last_time    = None
        self._held_keys   = set()

        self._tap       = None
        self._rl_source = None
        self._rl_thread = None
        self._run_loop  = None

    # Recording Logic
    def start_recording(self) -> None:
        self.events       = []
        self._held_keys   = set()
        self.is_recording = True
        self.last_time    = time.perf_counter()
        self._start_tap()

    def stop_recording(self, trim_keys: int = 0, trim_click: bool = False) -> None:
        self.is_recording = False
        self._stop_tap()

        # Remove the inputs used to trigger stop_recording itself
        if trim_keys > 0:
            removed = 0
            while self.events and removed < trim_keys:
                if self.events.pop()["type"] == "key_down":
                    removed += 1
        elif trim_click:
            while self.events:
                if self.events.pop()["type"] == "click_down":
                    break

    # Quartz tap 

    def _quartz_callback(self, proxy, event_type, event, refcon):
        if not self.is_recording:
            return event

        now = time.perf_counter()

        if event_type in _MOUSE_DOWN or event_type in _MOUSE_UP:
            loc   = CGEventGetLocation(event)
            btn_n = CGEventGetIntegerValueField(event, kCGMouseEventButtonNumber)
            btn_s = ("Button.left"   if btn_n == 0
                     else "Button.right"  if btn_n == 1
                     else "Button.middle")
            self.events.append({
                "type":   "click_down" if event_type in _MOUSE_DOWN else "click_up",
                "x":      loc.x,
                "y":      loc.y,
                "button": btn_s,
                "delay":  now - self.last_time,
            })
            self.last_time = now

        elif event_type == kCGEventKeyDown:
            code  = CGEventGetIntegerValueField(event, kCGKeyboardEventKeycode)
            key_s = f"cg:{code}"
            if key_s not in self._held_keys:
                self._held_keys.add(key_s)
                self.events.append({
                    "type":  "key_down",
                    "key":   key_s,
                    "delay": now - self.last_time,
                })
                self.last_time = now

        elif event_type == kCGEventKeyUp:
            code  = CGEventGetIntegerValueField(event, kCGKeyboardEventKeycode)
            key_s = f"cg:{code}"
            self._held_keys.discard(key_s)
            self.events.append({
                "type":  "key_up",
                "key":   key_s,
                "delay": now - self.last_time,
            })
            self.last_time = now

        return event

    def _start_tap(self) -> None:
        self._tap = CGEventTapCreate(
            kCGSessionEventTap,
            kCGHeadInsertEventTap,
            kCGEventTapOptionDefault,
            _MOUSE_MASK,
            self._quartz_callback,
            None,
        )
        if not self._tap:
            raise RuntimeError(
                "Could not create CGEventTap. "
                "Check Accessibility permission in System Settings."
            )

        self._rl_source = CFMachPortCreateRunLoopSource(None, self._tap, 0)

        def _run():
            self._run_loop = CFRunLoopGetCurrent()
            CFRunLoopAddSource(self._run_loop, self._rl_source, kCFRunLoopDefaultMode)
            CGEventTapEnable(self._tap, True)
            CFRunLoopRun()

        self._rl_thread = threading.Thread(target=_run, daemon=True)
        self._rl_thread.start()

    def _stop_tap(self) -> None:
        try:
            if self._tap:      CGEventTapEnable(self._tap, False)
            if self._run_loop: CFRunLoopStop(self._run_loop)
        except Exception as e:
            print(f"[Sally Clicks] Error stopping event tap: {e}", file=sys.stderr)
            logger.error(f"Error stopping event tap: {e}", exc_info=True)
        self._tap = self._rl_source = self._run_loop = None

    # Playback Logic

    def play_macro(
        self,
        on_complete_callback,
        loops: int = 1,
        on_event_callback=None,
        on_loop_callback=None,
    ) -> None:
        if not self.events or self.is_playing:
            return
        self.is_playing = True

        def _thread():
            iteration = 0
            while self.is_playing:
                if on_loop_callback:
                    try:
                        on_loop_callback(iteration, loops)
                    except Exception as e:
                        print(f"[Sally Clicks] Loop callback error: {e}", file=sys.stderr)
                        logger.error(f"Loop callback error: {e}", exc_info=True)

                t_start = time.perf_counter()
                cursor  = 0.0

                for i, event in enumerate(self.events):
                    if not self.is_playing:
                        break

                    # Enforce 1 ms minimum between events to prevent storms
                    raw_delay = event.get("delay", 0)
                    cursor   += max(raw_delay, MIN_DELAY)
                    target    = t_start + cursor

                    # High-resolution busy-wait in 0.5 ms chunks
                    while True:
                        remaining = target - time.perf_counter()
                        if remaining <= 0:
                            break
                        time.sleep(min(remaining, 0.0005))
                        if not self.is_playing:
                            break

                    if not self.is_playing:
                        break

                    input_handler.fire_event(event)

                    if on_event_callback:
                        try:
                            on_event_callback(i)
                        except Exception as e:
                            print(f"[Sally Clicks] Event callback error: {e}", file=sys.stderr)
                            logger.error(f"Event callback error: {e}", exc_info=True)

                iteration += 1
                if loops != -1 and iteration >= loops:
                    break

            self.is_playing = False
            input_handler.release_all()
            try:
                on_complete_callback()
            except Exception as e:
                print(f"[Sally Clicks] Completion callback error: {e}", file=sys.stderr)
                logger.error(f"Completion callback error: {e}", exc_info=True)

        threading.Thread(target=_thread, daemon=True).start()

    def stop_playback(self) -> None:
        self.is_playing = False

    @staticmethod
    def stitch(a: list, b: list) -> list:
        return list(a) + list(b)