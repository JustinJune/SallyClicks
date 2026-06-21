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
        self._item_geom  = []
        self.bind("<Configure>", lambda _e: self._draw())

    def load(self, events):
        self._events    = events
        self._highlight = -1
        self.xview_moveto(0)
        self._draw()

    def highlight(self, idx):
        if idx == self._highlight:
            return  

        prev = self._highlight
        self._highlight = idx

        
        if 0 <= prev < len(self._item_geom):
            item_id, base_col, _, _ = self._item_geom[prev]
            try:
                self.itemconfig(item_id, outline=base_col, width=0)
            except tk.TclError:
                pass  

        if 0 <= idx < len(self._item_geom):
            item_id, _, x1, x2 = self._item_geom[idx]
            try:
                self.itemconfig(item_id, outline=config.COLOR_TEXT, width=2)
                self._autoscroll_to(x1, x2)
            except tk.TclError:
                pass

    def _autoscroll_to(self, x1: float, x2: float):
        w = max(self.winfo_width(), 1)
        max_x = self._scroll_max_x or w
        left  = self.canvasx(0)
        right = self.canvasx(w)
        if x2 > right:
            self.xview_moveto((x2 - w + 20) / max_x)
        elif x1 < left:
            self.xview_moveto(max(0.0, (x1 - 20) / max_x))

    def _draw(self):
        self.delete("all")
        self._item_geom = []
        w = max(self.winfo_width(), 1)

        if not self._events:
            self.create_text(
                w // 2, 11, text="no events",
                fill=config.COLOR_MUTED, font=config.UI_FONT_MONO,
            )
            return

        total = sum(e.get("delay", 0) + e.get("duration", 0.05) for e in self._events)
        if total == 0:
            self._scroll_max_x = w
            return

        scale  = (w - 2 * self.PAD) / total
        x      = self.PAD
        y0     = (22 - self.BAR_H) // 2

        for i, ev in enumerate(self._events):
            x  += ev.get("delay", 0) * scale
            bw  = max(ev.get("duration", 0.05) * scale, self.MIN_PX)
            col = (config.COLOR_CLICK_EVT
                   if ev["type"] in ("click", "click_down", "click_up")
                   else config.COLOR_KEY_EVT)

            is_hl = (i == self._highlight)
            item_id = self.create_rectangle(
                x, y0, x + bw, y0 + self.BAR_H,
                fill=col, 
                outline=config.COLOR_TEXT if is_hl else col,
                width=2 if is_hl else 0,
            )
            self._item_geom.append((item_id, col, x, x + bw))
            x += bw

        max_x = x + self.PAD
        self._scroll_max_x = max_x
        self.config(scrollregion=(0, 0, max(w, max_x), 22))

        if 0 <= self._highlight < len(self._item_geom):
            _, _, x1, x2 = self._item_geom[self._highlight]
            self._autoscroll_to(x1, x2)