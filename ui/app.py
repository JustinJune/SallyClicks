# ui/app.py
import platform
import sys
import tkinter as tk
from tkinter import messagebox
from utils import persistence
import config
from ui.widgets import FlatBtn
from ui.slot_card import SlotCard
from ui.input_manager import GlobalInputManager
from ui.stitch_dialog import open_stitch_dialog
from ui.hotkey_manager import open_hotkey_manager
from ui.slot_card import filedialog
from ui.security_dialog import ask_security_lock



class AppGUI:
    MAX_SLOTS = 8

    def __init__(self, root: tk.Tk):
        self.root = root
        self.root.title(config.WINDOW_TITLE)
        self.root.configure(bg=config.COLOR_BG)
        self.root.attributes("-topmost", True)
        self.root.resizable(True, True)
        self.root.geometry(f"{config.WINDOW_W}x{config.WINDOW_H}")

        self.slots:        list[SlotCard] = []
        self._label_pool:  list[str]      = list(config.SLOT_LABELS)
        self._observers:   list           = []

        self.input_manager   = GlobalInputManager(self)
        self.hk_global_stop  = frozenset()

        self._build_chrome()
        self._add_slot()

        self.root.bind_all("<Button-1>", self._on_global_click, add="+")

    # --- Observer / notification ---

    def notify_change(self):
        for cb in self._observers:
            try:
                cb()
            except Exception as e:
                 print(f"[Sally Clicks] Observer error: {e}", file=sys.stderr)

    def _on_global_click(self, event):
        if event.widget and not isinstance(event.widget, tk.Entry):
            if isinstance(self.root.focus_get(), tk.Entry):
                self.root.focus_set()

    # --- Hotkey binding ---

    def start_binding(self, action_tuple, btn_widget):
        if self.input_manager.binding_action is not None:
            return
        self.root.focus_set()
        btn_widget.update_style(text="Press…", bg=config.COLOR_RED_LT)
        self.input_manager.binding_action     = action_tuple
        self.input_manager.active_bind_btn    = btn_widget
        self.input_manager.current_bind_combo = set()
        self.input_manager.held_keys.clear()

    def update_bind_ui(self, slot, action, combo_str):
        if self.input_manager.active_bind_btn:
            self.input_manager.active_bind_btn.update_style(text=combo_str)

    def finish_binding(self, action_tuple, frozen_combo):
        slot, action = action_tuple

        # Only check for duplicates if the user actually pressed a key 
        if frozen_combo:
            conflict_name = None

            # Check Global Stop
            if self.hk_global_stop == frozen_combo and slot != "__global__":
                conflict_name = "Global Stop"

            # Check all individual slots
            if not conflict_name:
                for s in self.slots:
                    if s.hk_rec == frozen_combo and not (s == slot and action == "rec"):
                        conflict_name = f"{s.get_name()} (Record)"
                        break
                    if s.hk_play == frozen_combo and not (s == slot and action == "play"):
                        conflict_name = f"{s.get_name()} (Play)"
                        break
                    if s.hk_stop == frozen_combo and not (s == slot and action == "stop"):
                        conflict_name = f"{s.get_name()} (Stop)"
                        break

            # If a duplicate is found, warn the user and revert to the previous key
            if conflict_name:
                messagebox.showwarning(
                    "Hotkey in Use",
                    f"That combination is already assigned to:\n{conflict_name}\n\n"
                    "Please choose a unique hotkey.",
                    parent=self.root
                )
                # Revert to the existing binding so we don't accidentally wipe it
                if slot == "__global__":
                    frozen_combo = self.hk_global_stop
                else:
                    frozen_combo = getattr(slot, f"hk_{action}")

        # This applies either the new hotkey, the reverted hotkey, or unbinds it
        if slot == "__global__":
            self.hk_global_stop = frozen_combo
        else:
            slot.set_binding(action, frozen_combo)

        # Update the UI button to reflect the final state
        if self.input_manager.active_bind_btn:
            label = " + ".join(sorted(frozen_combo)) if frozen_combo else "Unbound"
            self.input_manager.active_bind_btn.update_style(text=label, bg=config.COLOR_BG)
            self.input_manager.active_bind_btn = None

    def check_hotkeys(self, frozen_keys):
        if not frozen_keys:
            return
        if isinstance(self.root.focus_get(), tk.Entry):
            return

        if self.hk_global_stop and frozen_keys == self.hk_global_stop:
            self._global_stop_all()
            self.input_manager.held_keys.clear()
            return

        for slot in self.slots:
            if frozen_keys == slot.hk_rec and not slot.engine.is_playing:
                slot.toggle_record(is_hotkey=True)
                self.input_manager.held_keys.clear()
            elif frozen_keys == slot.hk_play and not slot.engine.is_recording:
                slot.play()
                self.input_manager.held_keys.clear()
            elif frozen_keys == slot.hk_stop:
                slot.stop()
                self.input_manager.held_keys.clear()

    def _global_stop_all(self):
        for slot in self.slots:
            try:
                if slot.engine.is_playing:   slot.stop()
                if slot.engine.is_recording: slot.toggle_record()
            except Exception as e:
                print(f"[Sally Clicks] Error stopping slot: {e}", file=sys.stderr)

    # ── Chrome (toolbar + card canvas) ───────────────────────────────────────

    def _build_chrome(self):
        P = config.COLOR_PANEL
        B = config.COLOR_BG

        # Toolbar at the bottom so it's last to be hidden when window shrinks
        toolbar = tk.Frame(
            self.root, bg=P,
            highlightthickness=1, highlightbackground=config.COLOR_BORDER,
            pady=7,
        )
        toolbar.pack(fill="x", side="bottom")
        tk.Label(toolbar, text="○ Sally Clicks!",
                 font=("Arial", 13, "bold"),
                 fg=config.COLOR_ACCENT, bg=P).pack(side="left", padx=12)

        FlatBtn(toolbar, text="📂 Load Session",
                font=config.UI_FONT, fg=config.COLOR_TEXT_MED,
                bg=config.COLOR_BG, active_bg=config.COLOR_BORDER,
                cmd=self._load_session,
                ).pack(side="left", padx=(16, 0))

        FlatBtn(toolbar, text="💾 Save Session",
                font=config.UI_FONT, fg=config.COLOR_TEXT_MED,
                bg=config.COLOR_BG, active_bg=config.COLOR_BORDER,
                cmd=self._save_session,
                ).pack(side="left", padx=(8, 0))

        FlatBtn(toolbar, text="⌨ Hotkeys",
                font=config.UI_FONT, fg=config.COLOR_TEXT,
                bg=config.COLOR_PANEL_HDR, active_bg=config.COLOR_BORDER,
                cmd=lambda: open_hotkey_manager(self),
                ).pack(side="right", padx=(0, 8))
        FlatBtn(toolbar, text="🔗 Stitch…",
                font=config.UI_FONT, fg=config.COLOR_TEXT,
                bg=config.COLOR_ACCENT_LT, active_bg=config.COLOR_BORDER,
                cmd=lambda: open_stitch_dialog(self),
                ).pack(side="right", padx=(0, 8))
        FlatBtn(toolbar, text="+ Add Slot",
                font=config.UI_FONT, fg=config.COLOR_PANEL,
                bg=config.COLOR_ACCENT, active_bg="#1D4ED8",
                cmd=self._add_slot,
                ).pack(side="right", padx=(0, 8))

        # Card scroll area
        outer = tk.Frame(self.root, bg=B, highlightthickness=0, bd=0)
        outer.pack(fill="both", expand=True, padx=10, pady=10)

        self._canvas = tk.Canvas(outer, bg=B, highlightthickness=0, bd=0)

        hscroll = tk.Scrollbar(outer, orient="horizontal",
                               command=self._canvas.xview,
                               bg=P, troughcolor=B)
        self._canvas.configure(xscrollcommand=hscroll.set)
        hscroll.pack(side="bottom", fill="x")

        vscroll = tk.Scrollbar(outer, orient="vertical",
                               command=self._canvas.yview,
                               bg=P, troughcolor=B)
        self._canvas.configure(yscrollcommand=vscroll.set)
        vscroll.pack(side="right", fill="y")

        self._canvas.pack(fill="both", expand=True)

        self._cards_frame = tk.Frame(self._canvas, bg=B, highlightthickness=0, bd=0)
        self._cw = self._canvas.create_window((0, 0), window=self._cards_frame, anchor="nw")
        self._cards_frame.bind(
            "<Configure>",
            lambda _: self._canvas.configure(scrollregion=self._canvas.bbox("all")),
        )
        self._canvas.bind(
            "<Configure>",
            lambda e: self._canvas.itemconfig(self._cw, height=e.height),
        )

        _plt = platform.system()

        def _scroll_h(event):
            if isinstance(event.widget, tk.Listbox): return
            amt = int(-event.delta) if _plt == "Darwin" else int(-event.delta / 120)
            if amt: self._canvas.xview_scroll(amt, "units")

        def _scroll_v(event):
            if isinstance(event.widget, tk.Listbox): return
            amt = int(-event.delta) if _plt == "Darwin" else int(-event.delta / 120)
            if amt: self._canvas.yview_scroll(amt, "units")

        self.root.bind_all("<MouseWheel>",       _scroll_v)
        self.root.bind_all("<Shift-MouseWheel>", _scroll_h)

    # ── Slot management ───────────────────────────────────────────────────────

    def _take_label(self) -> str:
        return self._label_pool.pop(0) if self._label_pool else f"#{len(self.slots)+1}"

    def _return_label(self, lbl: str):
        if lbl in config.SLOT_LABELS and lbl not in self._label_pool:
            self._label_pool.append(lbl)
            self._label_pool.sort(
                key=lambda x: config.SLOT_LABELS.index(x) if x in config.SLOT_LABELS else 999
            )

    def _add_slot(self, custom_label=None):
        if len(self.slots) >= self.MAX_SLOTS:
            messagebox.showinfo("Limit", f"Maximum {self.MAX_SLOTS} slots.", parent=self.root)
            return None
        lbl  = custom_label or self._take_label()
        card = SlotCard(
            self._cards_frame, label=lbl, master_app=self,
            on_remove=lambda c=None, l=lbl: self._remove_slot(card, l),
        )
        card.pack(side="left", fill="y", padx=(0, 8))
        self.slots.append(card)
        self.notify_change()
        return card

    def _remove_slot(self, card: SlotCard, lbl: str):
        if len(self.slots) == 1: return
        if card.engine.is_recording or card.engine.is_playing: return
        card.engine.stop_playback()
        card.destroy()
        self.slots.remove(card)
        self._return_label(lbl)
        self.notify_change()

    # --- Save and loading session ---
    def _save_session(self):
        fp = filedialog.asksaveasfilename(
            parent=self.root,
            title="Save Global Workspace",
            defaultextension=".json",
            filetypes=[("JSON Session", "*.json")],
            initialfile= "DEFAULT_SESSION_FILE",
        )
        if not fp:
            return

        # Trigger our cleanly imported UI dialog
        is_secure = ask_security_lock(self.root)
        
        # If the user closed the dialog window with the 'X', abort the save
        if is_secure is None:
            return

        session_data = {
            "global_stop": list(self.hk_global_stop),
            "slots": []
        }

        for slot in self.slots:
            has_data = (len(slot.get_events()) > 0 or slot.hk_rec or slot.hk_play or slot.hk_stop)
            if not has_data:
                continue

            session_data["slots"].append({
                "label": slot.label,
                "name": slot.get_name(),
                "events": slot.get_events(),
                "hk_rec": list(slot.hk_rec),
                "hk_play": list(slot.hk_play),
                "hk_stop": list(slot.hk_stop),
                "loops": slot._loop_var.get(),
                "inf": slot._inf_var.get(),
                "speed": slot._speed_var.get(),
            })

        if persistence.save_session(fp, session_data, is_secure=is_secure):
            msg = "Workspace securely locked to this Mac! 🔒" if is_secure else "Portable workspace saved successfully! ✓"
            messagebox.showinfo("Success", msg, parent=self.root)
        else:
            messagebox.showerror("Error", "Failed to save workspace.", parent=self.root)

    def _load_session(self):
        fp = filedialog.askopenfilename(
            parent=self.root,
            title="Load Global Workspace",
            filetypes=[("JSON Session", "*.json")],
        )
        if not fp:
            return

        session_data, err = persistence.load_session(fp)

        if err:
            messagebox.showerror("Load Failed", err, parent=self.root)
            return

        # --- Wipe the current board ---
        for slot in list(self.slots):
            slot.engine.stop_playback()
            slot.destroy()
        self.slots.clear()
        self._label_pool = list(config.SLOT_LABELS)

        # --- Restore Global State ---
        loaded_global = session_data.get("global_stop", [])
        if loaded_global or not self.hk_global_stop:
            self.hk_global_stop = frozenset(loaded_global)

        # --- Rebuild Slots ---
        for s_data in session_data.get("slots", []):
            slot = self._add_slot(custom_label=s_data.get("label"))
            if not slot: 
                continue

            # Restore Text & Events
            slot._name_var.set(s_data.get("name", f"Macro {slot.label}"))
            slot.engine.events = s_data.get("events", [])
            slot._refresh_list()
            if slot.engine.events:
                slot._set_status(f"{len(slot.engine.events)} events", config.COLOR_ACCENT)

            # Restore Hotkeys (Convert list -> frozenset)
            slot.hk_rec = frozenset(s_data.get("hk_rec", []))
            slot.hk_play = frozenset(s_data.get("hk_play", []))
            slot.hk_stop = frozenset(s_data.get("hk_stop", []))

            # Restore Configurations
            slot._loop_var.set(s_data.get("loops", "1"))
            slot._inf_var.set(s_data.get("inf", False))
            slot._toggle_inf()
            slot._speed_var.set(s_data.get("speed", "1.0x"))

        self.notify_change()
        messagebox.showinfo("Success", "Workspace fully restored!", parent=self.root)
    