# ui/timeline.py
import tkinter as tk
import config


class MiniTimeline(tk.Canvas):
    BAR_H  = 12
    PAD    = 4
    MIN_PX = 4

    def __init__(self, parent, **kw):
        super().__init__(
            parent, height=22,
            bg=config.COLOR_PANEL,
            highlightthickness=0, bd=0, **kw,
        )
        self._events    = []
        self._highlight = -1
        self.bind("<Configure>", lambda _e: self._draw())

    def load(self, events):
        self._events    = events
        self._highlight = -1
        self.xview_moveto(0)
        self._draw()

    def highlight(self, idx):
        self._highlight = idx
        self._draw()

    def _draw(self):
        self.delete("all")
        w = max(self.winfo_width(), 1)

        if not self._events:
            self.create_text(
                w // 2, 11, text="no events",
                fill=config.COLOR_MUTED, font=config.UI_FONT_MONO,
            )
            return

        total = sum(e.get("delay", 0) + e.get("duration", 0.05) for e in self._events)
        if total == 0:
            return

        scale  = (w - 2 * self.PAD) / total
        x      = self.PAD
        y0     = (22 - self.BAR_H) // 2
        hl_x1  = hl_x2 = 0

        for i, ev in enumerate(self._events):
            x  += ev.get("delay", 0) * scale
            bw  = max(ev.get("duration", 0.05) * scale, self.MIN_PX)
            col = (config.COLOR_CLICK_EVT
                   if ev["type"] in ("click", "click_down", "click_up")
                   else config.COLOR_KEY_EVT)
            ow  = 2 if i == self._highlight else 0
            out = config.COLOR_TEXT if i == self._highlight else col

            self.create_rectangle(
                x, y0, x + bw, y0 + self.BAR_H,
                fill=col, outline=out, width=ow,
            )

            if i == self._highlight:
                hl_x1, hl_x2 = x, x + bw

            x += bw

        max_x = x + self.PAD
        self.config(scrollregion=(0, 0, max(w, max_x), 22))

        if self._highlight >= 0:
            left  = self.canvasx(0)
            right = self.canvasx(w)
            if hl_x2 > right:
                self.xview_moveto((hl_x2 - w + 20) / max_x)
            elif hl_x1 < left:
                self.xview_moveto(max(0.0, (hl_x1 - 20) / max_x))