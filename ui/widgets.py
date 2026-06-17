# ui/widgets.py
import tkinter as tk
import config


# ── Helpers ───────────────────────────────────────────────────────────────────

def fmt_ms(seconds: float) -> str:
    return f"{int(seconds * 1000)} ms"


def event_label(ev: dict) -> str:
    t = ev["type"]
    if t == "click_down": return f"↙ ({ev.get('x',0)},{ev.get('y',0)})"
    if t == "click_up":   return f"↖ ({ev.get('x',0)},{ev.get('y',0)})"
    if t == "key_down":   return f"↓ {ev.get('key','?')}"
    if t == "key_up":     return f"↑ {ev.get('key','?')}"
    return f"⌨ {ev.get('key','?')}  {fmt_ms(ev.get('duration', 0))}"


# ── FlatBtn ───────────────────────────────────────────────────────────────────

class FlatBtn(tk.Frame):
    """Borderless button — avoids macOS black-border and dimming artifacts."""

    def __init__(self, parent, text, fg, bg, active_bg, cmd, font,
                 pad_x=6, pad_y=3, disabled=False):
        super().__init__(parent, bg=bg)
        self.normal_bg   = bg
        self.active_bg   = active_bg
        self.normal_fg   = fg
        self.disabled_fg = config.COLOR_MUTED
        self.cmd         = cmd
        self.is_disabled = disabled

        self.lbl = tk.Label(
            self, text=text,
            fg=self.disabled_fg if disabled else fg,
            bg=bg, font=font,
            cursor="arrow" if disabled else "hand2",
        )
        self.lbl.pack(padx=pad_x, pady=pad_y)
        self.lbl.bind("<Enter>",    self._on_enter)
        self.lbl.bind("<Leave>",    self._on_leave)
        self.lbl.bind("<Button-1>", self._on_click)

    def _on_enter(self, _):
        if not self.is_disabled:
            self.config(bg=self.active_bg)
            self.lbl.config(bg=self.active_bg)

    def _on_leave(self, _):
        if not self.is_disabled:
            self.config(bg=self.normal_bg)
            self.lbl.config(bg=self.normal_bg)

    def _on_click(self, _):
        if not self.is_disabled and self.cmd:
            self.cmd()

    def config_state(self, state: str):
        self.is_disabled = (state == "disabled")
        self.lbl.config(
            cursor="arrow" if self.is_disabled else "hand2",
            fg=self.disabled_fg if self.is_disabled else self.normal_fg,
        )
        if self.is_disabled:
            self.config(bg=self.normal_bg)
            self.lbl.config(bg=self.normal_bg)

    def update_style(self, text=None, fg=None, bg=None, active_bg=None):
        if text       is not None: self.lbl.config(text=text)
        if fg         is not None:
            self.normal_fg = fg
            if not self.is_disabled: self.lbl.config(fg=fg)
        if bg         is not None:
            self.normal_bg = bg
            if not self.is_disabled:
                self.config(bg=bg)
                self.lbl.config(bg=bg)
        if active_bg  is not None:
            self.active_bg = active_bg