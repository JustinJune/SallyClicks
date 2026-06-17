# ui/stitch_dialog.py
import tkinter as tk
from tkinter import messagebox

import config
from ui.widgets import FlatBtn


def open_stitch_dialog(app):
    """
    Open the drag-and-drop stitch dialog.
    `app` is the AppGUI instance (provides .slots, ._add_slot, .root).

    Drag fix: rows are never destroyed during a drag. Only the pack order is
    swapped, so all child widgets stay intact and visible throughout.
    """

    # Gather slots that actually have events
    items = [s for s in app.slots if hasattr(s, "engine") and s.get_events()]

    if len(items) < 2:
        messagebox.showinfo(
            "Stitch",
            "Need at least 2 slots with recorded events to stitch.",
            parent=app.root,
        )
        return

    # ── Window ───────────────────────────────────────────────────────────────
    dlg = tk.Toplevel(app.root)
    dlg.title("Stitch Macros")
    x = app.root.winfo_rootx() + app.root.winfo_width() + 10
    y = app.root.winfo_rooty()
    dlg.geometry(f"440x560+{x}+{y}")
    dlg.resizable(False, False)
    dlg.configure(bg=config.COLOR_BG)
    dlg.attributes("-topmost", True)
    dlg.lift()

    # ── Header ───────────────────────────────────────────────────────────────
    hdr = tk.Frame(dlg, bg=config.COLOR_PANEL,
                   highlightthickness=1, highlightbackground=config.COLOR_BORDER)
    hdr.pack(fill="x")
    tk.Label(hdr, text="🔗  Stitch Macros",
             font=("Arial", 13, "bold"), fg=config.COLOR_ACCENT,
             bg=config.COLOR_PANEL).pack(side="left", padx=14, pady=10)
    tk.Label(hdr, text="Drag to reorder  ·  × to remove",
             font=config.UI_FONT_MONO, fg=config.COLOR_MUTED,
             bg=config.COLOR_PANEL).pack(side="left")

    # ── Row list ─────────────────────────────────────────────────────────────
    list_outer = tk.Frame(dlg, bg=config.COLOR_BG)
    list_outer.pack(fill="both", expand=True, padx=16, pady=12)

    ROW_H     = 56
    IDLE_BG   = config.COLOR_PANEL
    DRAG_BG   = config.COLOR_ACCENT_LT   # highlight on the source row while dragging
    GHOST_BG  = "#E2E8F0"                # muted placeholder colour

    # Each entry: {"slot": SlotCard, "frame": tk.Frame, "badge": tk.Label}
    rows: list[dict] = []

    # ── Preview ───────────────────────────────────────────────────────────────
    preview_frame = tk.Frame(dlg, bg=config.COLOR_PANEL,
                             highlightthickness=1,
                             highlightbackground=config.COLOR_BORDER)
    preview_frame.pack(fill="x", padx=16, pady=(0, 8))
    tk.Label(preview_frame, text="Sequence preview:",
             font=config.UI_FONT_MONO, fg=config.COLOR_MUTED,
             bg=config.COLOR_PANEL).pack(anchor="w", padx=10, pady=(6, 2))
    _preview_var = tk.StringVar(value="(no items)")
    tk.Label(preview_frame, textvariable=_preview_var,
             font=("Arial", 10, "bold"), fg=config.COLOR_TEXT,
             bg=config.COLOR_PANEL, anchor="w", wraplength=400,
             justify="left").pack(fill="x", padx=10, pady=(0, 8))

    def _update_preview():
        if not rows:
            _preview_var.set("(no items)")
            return
        names  = [r["slot"].get_name() for r in rows]
        total  = sum(len(r["slot"].get_events()) for r in rows)
        _preview_var.set("  →  ".join(names) + f"\n{total} total events")

    # ── "Add slot" dropdown ───────────────────────────────────────────────────
    add_frame = tk.Frame(dlg, bg=config.COLOR_PANEL,
                         highlightthickness=1,
                         highlightbackground=config.COLOR_BORDER)
    add_frame.pack(fill="x", padx=16, pady=(0, 8))
    tk.Label(add_frame, text="Add to sequence:",
             font=config.UI_FONT_MONO, fg=config.COLOR_TEXT,
             bg=config.COLOR_PANEL).pack(side="left", padx=10, pady=8)

    _sel_add = tk.StringVar()
    _om = tk.OptionMenu(add_frame, _sel_add, "")
    _om.config(font=config.UI_FONT, bg=config.COLOR_BG, fg=config.COLOR_TEXT,
               highlightthickness=0, bd=0)
    _om.pack(side="left", fill="x", expand=True, padx=(0, 10))

    def _refresh_add_menu():
        menu = _om["menu"]
        menu.delete(0, "end")
        opts = [s.get_name() for s in app.slots
                if hasattr(s, "engine") and s.get_events()]
        if not opts:
            _sel_add.set("")
            return
        if _sel_add.get() not in opts:
            _sel_add.set(opts[0])
        for opt in opts:
            menu.add_command(label=opt, command=tk._setit(_sel_add, opt))

    def _add_to_stitch():
        target = _sel_add.get()
        for s in app.slots:
            if s.get_name() == target:
                _append_row(s)
                _update_preview()
                break

    FlatBtn(add_frame, text="+ Add",
            font=config.UI_FONT_BOLD,
            fg=config.COLOR_PANEL, bg=config.COLOR_ACCENT, active_bg="#1D4ED8",
            cmd=_add_to_stitch, pad_x=12, pad_y=4).pack(side="right", padx=10, pady=6)

    # ── Row builder ───────────────────────────────────────────────────────────

    def _append_row(slot_obj):
        """Build one row frame and append it to `rows`."""
        idx   = len(rows)
        frame = tk.Frame(list_outer, bg=IDLE_BG,
                         highlightthickness=1,
                         highlightbackground=config.COLOR_BORDER,
                         height=ROW_H)
        frame.pack(fill="x", pady=(0, 6))
        frame.pack_propagate(False)

        grip = tk.Label(frame, text="⠿", font=("Arial", 16),
                        fg=config.COLOR_MUTED, bg=IDLE_BG, cursor="fleur")
        grip.pack(side="left", padx=(10, 6))

        badge = tk.Label(frame, text=str(idx + 1),
                         font=("Arial", 10, "bold"),
                         fg=config.COLOR_PANEL, bg=config.COLOR_ACCENT, width=2)
        badge.pack(side="left", padx=(0, 8))

        info = tk.Frame(frame, bg=IDLE_BG)
        info.pack(side="left", fill="both", expand=True)
        tk.Label(info, text=slot_obj.get_name(),
                 font=config.UI_FONT_BOLD, fg=config.COLOR_TEXT,
                 bg=IDLE_BG, anchor="w").pack(fill="x")
        tk.Label(info, text=f"{len(slot_obj.get_events())} events",
                 font=config.UI_FONT_MONO, fg=config.COLOR_MUTED,
                 bg=IDLE_BG, anchor="w").pack(fill="x")

        row_data = {"slot": slot_obj, "frame": frame, "badge": badge,
                    "grip": grip, "info": info}

        def _remove():
            rows.remove(row_data)
            frame.destroy()
            _renumber()
            _update_preview()

        FlatBtn(frame, text="×", font=("Arial", 14, "bold"),
                fg=config.COLOR_MUTED, bg=IDLE_BG, active_bg=config.COLOR_RED_LT,
                cmd=_remove).pack(side="right", padx=8)

        # ── Drag-and-drop ─────────────────────────────────────────────────────
        # Key design: we NEVER destroy rows during a drag.
        # We only swap them in the `rows` list and re-pack the frames.
        # All child widgets remain intact → no disappearing content.

        drag = {"src": None, "ghost": None, "ox": 0, "oy": 0}

        def _drag_start(e):
            drag["src"] = next(
                (i for i, r in enumerate(rows) if r is row_data), None
            )
            drag["ox"] = e.x_root - frame.winfo_rootx()
            drag["oy"] = e.y_root - frame.winfo_rooty()

            # Ghost window follows the cursor
            g = tk.Toplevel(dlg)
            g.overrideredirect(True)
            g.attributes("-topmost", True)
            g.geometry(
                f"{frame.winfo_width()}x{ROW_H}"
                f"+{e.x_root - drag['ox']}+{e.y_root - drag['oy']}"
            )
            g.configure(bg=DRAG_BG,
                        highlightthickness=2,
                        highlightbackground=config.COLOR_ACCENT)
            tk.Label(g,
                     text=f"⠿   {slot_obj.get_name()}",
                     font=config.UI_FONT_BOLD,
                     bg=DRAG_BG, fg=config.COLOR_TEXT).pack(
                         side="left", padx=10, pady=10)
            drag["ghost"] = g

            # Dim the source row in-place (don't touch children's text/widgets)
            frame.config(bg=GHOST_BG, highlightbackground=GHOST_BG)
            for w in [grip, badge, info] + list(info.winfo_children()):
                try:
                    w.config(bg=GHOST_BG)
                except Exception:
                    pass

        def _drag_motion(e):
            g = drag["ghost"]
            if not g:
                return
            g.geometry(f"+{e.x_root - drag['ox']}+{e.y_root - drag['oy']}")

            # Determine target index from cursor y relative to list_outer
            rel_y   = e.y_root - list_outer.winfo_rooty()
            tgt_idx = max(0, min(int(rel_y // (ROW_H + 6)), len(rows) - 1))
            src_idx = drag["src"]

            if tgt_idx != src_idx and src_idx is not None:
                # Swap in rows list
                rows[src_idx], rows[tgt_idx] = rows[tgt_idx], rows[src_idx]
                drag["src"] = tgt_idx

                # Re-pack all frames in new order (no destroy — just forget/repack)
                for r in rows:
                    r["frame"].pack_forget()
                for r in rows:
                    r["frame"].pack(fill="x", pady=(0, 6))

                _renumber()
                _update_preview()

        def _drag_end(e):
            g = drag.pop("ghost", None)
            if g:
                try:
                    g.destroy()
                except Exception:
                    pass

            # Restore source row colours
            frame.config(bg=IDLE_BG, highlightbackground=config.COLOR_BORDER)
            for w in [grip, badge, info] + list(info.winfo_children()):
                try:
                    w.config(bg=IDLE_BG)
                except Exception:
                    pass
            # Badge bg should stay accent blue
            badge.config(bg=config.COLOR_ACCENT)

        for w in [frame, grip, info, badge] + list(info.winfo_children()):
            w.bind("<ButtonPress-1>",  _drag_start)
            w.bind("<B1-Motion>",      _drag_motion)
            w.bind("<ButtonRelease-1>", _drag_end)

        rows.append(row_data)

    def _renumber():
        for i, r in enumerate(rows):
            r["badge"].config(text=str(i + 1))

    # ── Footer ────────────────────────────────────────────────────────────────
    footer = tk.Frame(dlg, bg=config.COLOR_BG)
    footer.pack(fill="x", padx=16, pady=(0, 16))

    def _do_stitch():
        if len(rows) < 2:
            messagebox.showwarning("Stitch", "Need at least 2 macros.", parent=dlg)
            return
        final_events, names = [], []
        for r in rows:
            final_events.extend(r["slot"].get_events())
            names.append(r["slot"].get_name().replace("Macro ", "").strip())

        new_slot = app._add_slot(custom_label=f"Stitch {'/'.join(names)}")
        if new_slot:
            new_slot.engine.events = final_events
            new_slot._refresh_list()
            new_slot._set_status(f"{len(final_events)} events", config.COLOR_ACCENT)
        dlg.destroy()

    FlatBtn(footer, text="✓  Create Stitched Macro",
            font=config.UI_FONT_BOLD,
            fg=config.COLOR_PANEL, bg=config.COLOR_ACCENT, active_bg="#1D4ED8",
            cmd=_do_stitch).pack(side="left")
    FlatBtn(footer, text="Cancel",
            font=config.UI_FONT,
            fg=config.COLOR_TEXT_MED, bg=config.COLOR_PANEL_HDR,
            active_bg=config.COLOR_BORDER,
            cmd=dlg.destroy).pack(side="left", padx=(8, 0))

    # ── Populate initial rows ─────────────────────────────────────────────────
    for slot in items:
        _append_row(slot)

    _refresh_add_menu()
    _update_preview()