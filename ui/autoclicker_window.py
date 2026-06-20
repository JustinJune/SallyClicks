# ui/autoclicker_window.py
import tkinter as tk
import config
from ui.widgets import FlatBtn

def open_autoclicker_window(app):
    if (
        hasattr(app, "ac_window")
        and app.ac_window
        and app.ac_window.winfo_exists()
    ):
        app.ac_window.lift()
        app.ac_window.focus_force()
        return

    win = tk.Toplevel(app.root)
    win.title("AutoClicker")
    win.geometry("240x140")
    win.configure(bg=config.COLOR_PANEL)

    win.attributes("-topmost", True)
    win.resizable(False, False)

    app.ac_window = win
    engine = app.autoclicker

    panel_color = config.COLOR_PANEL
    input_color = config.COLOR_BG

    # Status Section
    status_frame = tk.Frame(
        win,
        bg=panel_color
    )
    status_frame.pack(
        fill="x",
        padx=15,
        pady=(15, 0)
    )

    if engine.is_clicking:
        dot_color = config.COLOR_RED
        status_text = "Clicking!"
    else:
        dot_color = config.COLOR_MUTED
        status_text = "Ready"

    dot = tk.Label(
        status_frame,
        text="●",
        fg=dot_color,
        bg=panel_color,
        font=("Arial", 12)
    )
    dot.pack(side="left")

    status_var = tk.StringVar(value=status_text)

    status_label = tk.Label(
        status_frame,
        textvariable=status_var,
        font=("Arial", 11, "bold"),
        fg=config.COLOR_TEXT_MED,
        bg=panel_color
    )
    status_label.pack(
        side="left",
        padx=(4, 0)
    )

    # -------------------------
    # Hotkey Section
    # -------------------------

    control_frame = tk.Frame(
        win,
        bg=panel_color
    )
    control_frame.pack(
        fill="x",
        padx=15,
        pady=(10, 5)
    )

    hotkey_label = tk.Label(
        control_frame,
        text="Hotkey",
        font=("Arial", 11),
        fg=config.COLOR_MUTED,
        bg=panel_color
    )
    hotkey_label.pack(side="left")

    if app.hk_autoclick:
        current_bind = " + ".join(sorted(app.hk_autoclick))
    else:
        current_bind = "Unbound"

    btn_bind = FlatBtn(
        control_frame,
        text=current_bind,
        font=("Arial", 11),
        fg=config.COLOR_TEXT,
        bg=input_color,
        active_bg=config.COLOR_BORDER,
        cmd=lambda: app.start_binding(
            ("__autoclick__", "toggle"),
            btn_bind
        ),
        pad_x=10,
        pad_y=4
    )
    btn_bind.pack(side="right")

    # Interval Section
    settings_frame = tk.Frame(
        win,
        bg=panel_color
    )
    settings_frame.pack(
        fill="x",
        padx=15,
        pady=(5, 15)
    )

    interval_label = tk.Label(
        settings_frame,
        text="Interval",
        font=("Arial", 11),
        fg=config.COLOR_MUTED,
        bg=panel_color
    )
    interval_label.pack(side="left")

    validate_interval = (
        win.register(
            lambda value: (
                value.replace(".", "", 1).isdigit()
                or value == ""
            )
        ),
        "%P"
    )

    interval_units = tk.Label(
        settings_frame,
        text="ms",
        font=("Arial", 11),
        fg=config.COLOR_MUTED,
        bg=panel_color
    )
    interval_units.pack(
        side="right",
        padx=(0, 4)
    )

    interval_entry = tk.Entry(
        settings_frame,
        textvariable=app.ac_interval_var,
        width=5,
        justify="center", 
        font=("Arial", 14),
        bg=input_color,
        fg=config.COLOR_TEXT,
        insertbackground=config.COLOR_TEXT,
        relief="flat",
        highlightthickness=0,
        bd=0,
        validate="key",
        validatecommand=validate_interval
    )
    interval_entry.pack(
        side="right",
        ipady=2
    )

    def update_ui_state():
        if not win.winfo_exists():
            return

        if engine.is_clicking:
            status_var.set("Clicking!")
            dot.config(fg=config.COLOR_RED)
        else:
            status_var.set("Ready")
            dot.config(fg=config.COLOR_MUTED)

    win.update_ui_state = update_ui_state