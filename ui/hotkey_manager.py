# ui/hotkey_manager.py
import tkinter as tk

import config
from ui.widgets import FlatBtn


def open_hotkey_manager(app):
    """
    Open the hotkey manager window.
    `app` is the AppGUI instance.
    """
    win = tk.Toplevel(app.root)
    win.title("Global Hotkey Manager")
    x = app.root.winfo_rootx() + app.root.winfo_width() + 10
    y = app.root.winfo_rooty()
    win.geometry(f"400x550+{x}+{y}")
    win.configure(bg=config.COLOR_BG)
    win.attributes("-topmost", True)
    win.focus_force()

    # ── Global stop row ───────────────────────────────────────────────────────
    tk.Label(win, text="Bind keys for each macro:",
             font=config.UI_FONT_BOLD, bg=config.COLOR_BG,
             fg=config.COLOR_TEXT).pack(pady=10)

    g_frame = tk.LabelFrame(win, text=" Global Stop All ",
                            font=config.UI_FONT_BOLD,
                            bg=config.COLOR_RED_LT, fg=config.COLOR_RED)
    g_frame.pack(fill="x", padx=15, pady=(0, 6))
    g_row = tk.Frame(g_frame, bg=config.COLOR_RED_LT)
    g_row.pack(fill="x", padx=8, pady=6)
    tk.Label(g_row, text="Stop All Macros",
             bg=config.COLOR_RED_LT, font=config.UI_FONT_MONO,
             fg=config.COLOR_TEXT).pack(side="left", padx=(0, 12))

    g_btn = FlatBtn(
        g_row,
        text="Unbound" if not app.hk_global_stop
             else " + ".join(sorted(app.hk_global_stop)),
        font=config.UI_FONT_MONO, fg=config.COLOR_TEXT,
        bg=config.COLOR_BG, active_bg=config.COLOR_BORDER,
        cmd=lambda: None,
    )
    g_btn.cmd = lambda: app.start_binding(("__global__", "stop"), g_btn)
    g_btn.pack(side="left", fill="x", expand=True)

    # ── Per-slot rows ─────────────────────────────────────────────────────────
    container = tk.Frame(win, bg=config.COLOR_BG)
    container.pack(fill="both", expand=True, padx=10)

    def _rebuild():
        if app.input_manager.binding_action is not None:
            return
        
        if not app.hk_global_stop:
            g_btn.update_style(text="Unbound")
        else:
            g_btn.update_style(text=" + ".join(sorted(app.hk_global_stop)))

        # Rebuild the per-slot rows

        for w in container.winfo_children():
            w.destroy()

        for slot in app.slots:
            f = tk.LabelFrame(
                container, text=f" {slot.get_name()} ",
                font=config.UI_FONT_BOLD,
                bg=config.COLOR_PANEL, fg=config.COLOR_TEXT,
            )
            f.pack(fill="x", pady=5, padx=5)

            btn_row = tk.Frame(f, bg=config.COLOR_PANEL)
            btn_row.pack(fill="x", pady=6, padx=5)

            for action, label in [("rec", "Record"), ("play", "Play"), ("stop", "Stop")]:
                col = tk.Frame(btn_row, bg=config.COLOR_PANEL)
                col.pack(side="left", expand=True, fill="x", padx=4)
                tk.Label(col, text=label,
                         bg=config.COLOR_PANEL, font=config.UI_FONT_MONO,
                         fg=config.COLOR_TEXT_MED).pack(pady=(0, 2))
                btn = FlatBtn(
                    col, text="Unbound",
                    font=config.UI_FONT_MONO, fg=config.COLOR_TEXT,
                    bg=config.COLOR_BG, active_bg=config.COLOR_BORDER,
                    cmd=lambda: None,
                )
                btn.cmd = lambda s=slot, a=action, b=btn: app.start_binding((s, a), b)
                btn.pack(fill="x")
                current = getattr(slot, f"hk_{action}")
                if current:
                    btn.update_style(text=" + ".join(sorted(current)))

    def _on_close():
        if _rebuild in app._observers:
            app._observers.remove(_rebuild)
        win.destroy()

    win.protocol("WM_DELETE_WINDOW", _on_close)
    app._observers.append(_rebuild)
    _rebuild()