# ui/slot_card.py
import tkinter as tk
from tkinter import filedialog, messagebox

import config
from recorder import MacroEngine
from utils import persistence
from ui.widgets import FlatBtn, event_label
from ui.timeline import MiniTimeline
from ui.password_guard import warn_if_password_focused
from ui.security_dialog import ask_security_lock

class SlotCard(tk.Frame):
    CARD_W = 240

    def __init__(self, parent, label: str, master_app, on_remove, **kw):
        super().__init__(
            parent,
            bg=config.COLOR_PANEL, relief="flat",
            highlightthickness=1, highlightbackground=config.COLOR_BORDER,
            width=self.CARD_W, **kw,
        )
        self.label      = label
        self.master_app = master_app
        self._on_remove = on_remove
        self.engine     = MacroEngine()

        self._loop_var        = tk.StringVar(value="1")
        self._inf_var         = tk.BooleanVar(value=False)
        self._speed_var       = tk.StringVar(value="1.0x")
        self._log_open        = False
        self._original_events = None  # stores unscaled events during speed-scaled playback

        self.hk_rec  = frozenset()
        self.hk_play = frozenset()
        self.hk_stop = frozenset()

        self._build()
        self.propagate(False)

    # --- Build ---

    def _build(self):
        P, H, B = config.COLOR_PANEL, config.COLOR_PANEL_HDR, config.COLOR_BG

        # Header
        hdr = tk.Frame(self, bg=H, height=38, highlightthickness=0, bd=0)
        hdr.pack(fill="x")
        hdr.pack_propagate(False)

        self._name_var = tk.StringVar(value=f"Macro {self.label}")
        self._name_var.trace_add("write", lambda *_: self.master_app.notify_change())
        tk.Entry(
            hdr, textvariable=self._name_var, width=12,
            font=config.UI_FONT_BOLD, fg=config.COLOR_TEXT, bg=H,
            insertbackground=config.COLOR_TEXT, highlightthickness=0, relief="flat", bd=0,
        ).pack(side="left", padx=10, fill="y")

        FlatBtn(
            hdr, text="×", font=("Arial", 14, "bold"),
            fg=config.COLOR_MUTED, bg=H, active_bg=config.COLOR_RED_LT,
            cmd=self._on_remove, pad_x=10, pad_y=4,
        ).pack(side="right")

        # Timeline
        self.timeline = MiniTimeline(self)
        self.timeline.pack(fill="x", padx=8, pady=(8, 2))

        # Status
        sf = tk.Frame(self, bg=P, highlightthickness=0, bd=0)
        sf.pack(fill="x", padx=10, pady=(4, 0))
        self._dot = tk.Label(sf, text="●", fg=config.COLOR_MUTED, bg=P, font=("Arial", 12))
        self._dot.pack(side="left")
        self._status_var = tk.StringVar(value="Ready")
        tk.Label(
            sf, textvariable=self._status_var,
            font=("Arial", 11, "bold"), fg=config.COLOR_TEXT_MED, bg=P, anchor="w",
        ).pack(side="left", padx=(4, 0))

        # Controls
        ctrl = tk.Frame(self, bg=P, highlightthickness=0, bd=0)
        ctrl.pack(fill="x", padx=8, pady=(4, 4))
        self.btn_rec  = FlatBtn(ctrl, text="● Rec",  font=("Arial", 11, "bold"), fg=config.COLOR_RED,   bg=B, active_bg=config.COLOR_BORDER, cmd=self.toggle_record, pad_x=10, pad_y=6)
        self.btn_play = FlatBtn(ctrl, text="▶ Play", font=("Arial", 11, "bold"), fg=config.COLOR_GREEN, bg=B, active_bg=config.COLOR_BORDER, cmd=self.play,          pad_x=10, pad_y=6)
        self.btn_stop = FlatBtn(ctrl, text="■",      font=("Arial", 11, "bold"), fg=config.COLOR_MUTED, bg=B, active_bg=config.COLOR_BORDER, cmd=self.stop,          pad_x=10, pad_y=6, disabled=True)
        for b in (self.btn_rec, self.btn_play, self.btn_stop):
            b.pack(side="left", padx=2)

        # Loop + Speed
        lf = tk.Frame(self, bg=P, highlightthickness=0, bd=0)
        lf.pack(fill="x", padx=8, pady=(6, 10))

        tk.Checkbutton(
            lf, text="∞", variable=self._inf_var,
            font=("Arial", 16, "bold"), fg=config.COLOR_TEXT_MED, bg=P,
            selectcolor=config.COLOR_ACCENT_LT, activebackground=P,
            activeforeground=config.COLOR_TEXT, command=self._toggle_inf,
        ).pack(side="left", padx=(4, 10))

        vcmd = (self.register(lambda v: v.isdigit() or v == ""), "%P")
        self._loop_entry = tk.Entry(
            lf, textvariable=self._loop_var, width=3, font=("Arial", 14),
            bg=B, fg=config.COLOR_TEXT, insertbackground=config.COLOR_TEXT,
            disabledbackground=config.COLOR_PANEL_HDR, disabledforeground=config.COLOR_MUTED,
            relief="flat", highlightthickness=0, bd=0,
            validate="key", validatecommand=vcmd,
        )
        self._loop_entry.pack(side="left", padx=(0, 4), ipady=2)
        tk.Label(lf, text="times", font=("Arial", 11), fg=config.COLOR_MUTED, bg=P).pack(side="left")

        tk.Frame(lf, bg=P).pack(side="left", fill="x", expand=True)  # spring spacer

        speed_opts = ["0.5x", "1.0x", "1.5x", "2.0x", "4.0x", "8.0x"]
        om = tk.OptionMenu(lf, self._speed_var, *speed_opts)
        om.config(font=("Arial", 12), bg=B, fg=config.COLOR_TEXT, highlightthickness=0, bd=0)
        om.pack(side="left", padx=(0, 6))
        tk.Label(lf, text="Speed", font=("Arial", 11), fg=config.COLOR_MUTED, bg=P).pack(side="left", padx=(0, 4))

        tk.Frame(self, bg=config.COLOR_BORDER, height=1, highlightthickness=0, bd=0).pack(fill="x", padx=8, pady=4)

        # Footer
        ff = tk.Frame(self, bg=P, highlightthickness=0, bd=0)
        ff.pack(fill="x", padx=8, pady=(0, 8))
        FlatBtn(ff, text="💾 Save", font=("Arial", 10), fg=config.COLOR_TEXT_MED, bg=B, active_bg=config.COLOR_BORDER, cmd=self.save,         pad_x=8, pad_y=4).pack(side="left", padx=(0, 4))
        FlatBtn(ff, text="📂 Load", font=("Arial", 10), fg=config.COLOR_TEXT_MED, bg=B, active_bg=config.COLOR_BORDER, cmd=self.load,         pad_x=8, pad_y=4).pack(side="left", padx=(0, 4))
        self._btn_log = FlatBtn(ff, text="Events ▸",   font=("Arial", 10, "bold"), fg=config.COLOR_ACCENT, bg=B, active_bg=config.COLOR_BORDER, cmd=self._toggle_log, pad_x=8, pad_y=4)
        self._btn_log.pack(side="right")

        # Hidden event log
        self._log_frame = tk.Frame(self, bg=P, highlightthickness=0, bd=0)
        sb = tk.Scrollbar(self._log_frame, bg=config.COLOR_PANEL_HDR, troughcolor=B, width=10)
        sb.pack(side="right", fill="y")
        self._listbox = tk.Listbox(
            self._log_frame, font=config.UI_FONT_MONO,
            fg=config.COLOR_TEXT_MED, bg=B,
            selectbackground=config.COLOR_ACCENT_LT, selectforeground=config.COLOR_TEXT,
            relief="flat", bd=0, highlightthickness=0, activestyle="none",
            yscrollcommand=sb.set, height=8,
        )
        self._listbox.pack(fill="both", expand=True, padx=(4, 0))
        sb.config(command=self._listbox.yview)

    # --- Internal helpers ---

    def _set_status(self, msg, dot=None):
        self._status_var.set(msg)
        self._dot.config(fg=dot or config.COLOR_MUTED)

    def _refresh_list(self):
        self._listbox.delete(0, "end")
        for ev in self.engine.events:
            self._listbox.insert("end", " " + event_label(ev))
        self.timeline.load(self.engine.events)

    def _toggle_inf(self):
        self._loop_entry.config(state="disabled" if self._inf_var.get() else "normal")

    def _loop_count(self) -> int:
        if self._inf_var.get():
            return -1
        v = self._loop_var.get()
        return max(int(v), 1) if v.isdigit() else 1

    def _toggle_log(self):
        self._log_open = not self._log_open
        if self._log_open:
            self._log_frame.pack(fill="both", expand=True, padx=8, pady=(0, 6))
            self._btn_log.update_style(text="Events ▾")
        else:
            self._log_frame.pack_forget()
            self._btn_log.update_style(text="Events ▸")

    def _scaled_events(self, speed: float) -> list:
        result = []
        for e in self.engine.events:
            ne = dict(e)
            if "delay"    in ne: ne["delay"]    = max(0, ne["delay"]    / speed)
            if "duration" in ne: ne["duration"] = max(0, ne["duration"] / speed)
            result.append(ne)
        return result

    # --- Public API ---

    def set_binding(self, action: str, combo: frozenset):
        setattr(self, f"hk_{action}", combo)

    def get_name(self)   -> str:  return self._name_var.get()
    def get_events(self) -> list:
        return self._original_events if self._original_events is not None else self.engine.events

    # --- Record ---

    def toggle_record(self, is_hotkey=False):
        if not self.engine.is_recording:
            # Check if a password field is focused before capturing any input
            if not warn_if_password_focused(self.master_app.root):
                return
            self.engine.start_recording()
            self.btn_rec.update_style(text="⏹ STOP REC", fg="#FFFFFF", bg="#DC2626", active_bg="#B91C1C")
            self.btn_play.config_state("disabled")
            self._set_status("Recording…", config.COLOR_RED)
        else:
            trim_count = len(self.hk_rec) if is_hotkey else 0
            self.engine.stop_recording(trim_keys=trim_count, trim_click=not is_hotkey)
            self.btn_rec.update_style(text="● Rec", fg=config.COLOR_RED, bg=config.COLOR_BG, active_bg=config.COLOR_BORDER)
            self.btn_play.config_state("normal")
            self._refresh_list()
            self._set_status(f"{len(self.engine.events)} events", config.COLOR_GREEN)
            self.master_app.notify_change()

    # --- Playback ---

    def play(self):
        if not self.engine.events:
            return
        loops = self._loop_count()
        self._set_status(f"Playing ×{'∞' if loops == -1 else loops}", config.COLOR_GREEN)
        self.btn_rec.config_state("disabled")
        self.btn_play.config_state("disabled")
        self.btn_stop.config_state("normal")

        try:    speed = float(self._speed_var.get().replace("x", ""))
        except: speed = 1.0

        if speed != 1.0:
            self._original_events = self.engine.events
            self.engine.events    = self._scaled_events(speed)

        self.engine.play_macro(
            on_complete_callback=self._on_done,
            loops=loops,
            on_event_callback=self._on_tick,
            on_loop_callback=self._on_loop,
        )

    def _on_loop(self, iteration, total_loops):
        if total_loops == -1:
            return
        remaining = total_loops - iteration
        try:
            self.after(0, lambda: self._set_status(f"Playing ×{remaining}", config.COLOR_GREEN))
        except tk.TclError:
            pass

    def _on_tick(self, idx):
        try:
            self.after(0, lambda i=idx: self._update_tick(i))
        except tk.TclError:
            pass

    def _update_tick(self, idx):
        try:
            self.timeline.highlight(idx)
            if self._log_open:
                self._listbox.see(idx)
                self._listbox.selection_clear(0, "end")
                self._listbox.selection_set(idx)
        except tk.TclError:
            pass

    def _on_done(self):
        try:
            self.after(0, self._reset_btns)
        except tk.TclError:
            pass

    def _reset_btns(self):
        if self._original_events is not None:
            self.engine.events    = self._original_events
            self._original_events = None
        self._set_status("Done", config.COLOR_ACCENT)
        self.btn_rec.config_state("normal")
        self.btn_play.config_state("normal")
        self.btn_stop.config_state("disabled")
        self.timeline.highlight(-1)

    def stop(self):
        self.engine.stop_playback()
        if self._original_events is not None:
            self.engine.events    = self._original_events
            self._original_events = None
        self.btn_stop.config_state("disabled")
        self._set_status("Stopped", config.COLOR_MUTED)

    # --- File I/O ---

    def save(self):
        if not self.engine.events:
            return
            
        fp = filedialog.asksaveasfilename(
            parent= self,
            title = "Save Macro",
            defaultextension=".json",
            filetypes=[("JSON Macro", "*.json")],
            initialfile=f"{self.get_name().replace(' ', '_')}.json",
        )
        if not fp:
            return
        # call secure dialog
        is_secure = ask_security_lock(self.master_app.root)

        # If the user closed the window using the 'X' button, abort the save
        if is_secure is None:
            return
        
        events_to_save = self.get_events()
        # Execute Save
        if persistence.save_macro(fp, events_to_save, is_secure=is_secure):
            status_text = "Saved (Locked) 🔒" if is_secure else "Saved ✓"
            self._set_status(status_text, config.COLOR_GREEN)

    def load(self):
        fp = filedialog.askopenfilename(
            parent=self.master_app.root, filetypes=[("JSON", "*.json")],
        )
        if not fp:
            return

        result = persistence.load_macro(fp)

        if result.error:
            messagebox.showerror("Load Failed", result.error, parent=self.master_app.root)
            return

        if not result.events:
            messagebox.showerror("Error", "File is empty.", parent=self.master_app.root)
            return

        # Legacy file (no checksum) — warn but allow
        if result.is_legacy:
            ok = messagebox.askyesno(
                "Unverified File",
                "This file was saved before Sally Clicks added integrity checking.\n\n"
                "Its contents cannot be verified. Load anyway?",
                icon="warning",
                parent=self.master_app.root,
                default="yes",
            )
            if not ok:
                return

        # Modifier key warning for any externally-sourced file
        if result.has_modifiers:
            ok = messagebox.askyesno(
                "⚠️  Modifier Keys Detected",
                "This macro uses system modifier keys (Cmd/Ctrl).\n\n"
                "Only load macros from sources you trust — modifier keys can "
                "trigger system shortcuts or destructive actions.\n\n"
                "Continue loading?",
                icon="warning",
                parent=self.master_app.root,
                default="no",
            )
            if not ok:
                return

        self.engine.events = result.events
        self._refresh_list()
        self._set_status(f"{len(result.events)} events", config.COLOR_ACCENT)
        self.master_app.notify_change()