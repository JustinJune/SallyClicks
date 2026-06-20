# autoclicker.py
import time
import threading
import input_handler

class AutoClickerEngine:
    def __init__(self):
        self.is_clicking = False
        self.interval_sec = 0.1  # Default 100ms

    def toggle(self, interval_ms: float):
        if self.is_clicking:
            self.is_clicking = False
        else:
            # Prevent going faster than 1ms 
            self.interval_sec = max(interval_ms / 1000.0, 0.001) 
            self.is_clicking = True
            threading.Thread(target=self._run, daemon=True).start()

    def _run(self):
        while self.is_clicking:
            t_start = time.perf_counter()

            # 0 = Left Click
            input_handler.native_click_current(0, True)
            time.sleep(0.005) 
            input_handler.native_click_current(0, False)

            while self.is_clicking:
                if time.perf_counter() - t_start >= self.interval_sec:
                    break
                time.sleep(0.001)