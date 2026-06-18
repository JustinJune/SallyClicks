# ui/security_dialog.py
# Shows a custom dialog asking the user if they want to securely lock the macro.
# Returns:
#   True  -> Yes, Lock It
#   False -> No, Keep Portable
#   None  -> Cancelled / Window closed
import tkinter as tk
import config
from ui.widgets import FlatBtn

def ask_security_lock(parent) -> bool | None:
    dlg = tk.Toplevel(parent)
    dlg.title("")
    dlg.configure(bg=config.COLOR_PANEL)
    dlg.resizable(False, False)
    dlg.attributes("-topmost", True)
    dlg.transient(parent)

    dlg.update_idletasks()
    w, h = 420, 220
    x = parent.winfo_rootx() + (parent.winfo_width() // 2) - (w // 2)
    y = parent.winfo_rooty() + (parent.winfo_height() // 2) - (h // 2)
    dlg.geometry(f"{w}x{h}+{x}+{y}")

    container = tk.Frame(dlg, bg=config.COLOR_PANEL)
    container.pack(fill="both", expand=True, padx=24, pady=24)

    # Title
    tk.Label(
        container, text="🔒  Security Lock",
        font=("Arial", 16, "bold"), fg=config.COLOR_TEXT, bg=config.COLOR_PANEL, anchor="w"
    ).pack(fill="x", pady=(0, 12))

    # Description Text
    desc_text = (
        "Would you like to securely lock this macro to this Mac?\n\n"
        "Locked macros are hardware-encrypted but cannot be shared. "
        "Portable macros are saved as standard plain text."
    )
    tk.Label(
        container, text=desc_text,
        font=("Arial", 12), fg=config.COLOR_TEXT_MED, bg=config.COLOR_PANEL,
        justify="left", anchor="w", wraplength=372
    ).pack(fill="x", pady=(0, 24))

    btn_frame = tk.Frame(container, bg=config.COLOR_PANEL)
    btn_frame.pack(fill="x", side="bottom")

    result = {"choice": None}

    def _set_choice(choice):
        result["choice"] = choice
        dlg.destroy()

    # Left Button (Lock)
    FlatBtn(
        btn_frame, text="Yes, Lock It", font=config.UI_FONT_BOLD,
        fg=config.COLOR_TEXT_MED, bg=config.COLOR_BG, active_bg=config.COLOR_BORDER,
        cmd=lambda: _set_choice(True), pad_x=16, pad_y=6
    ).pack(side="left", padx=(0, 8)) 

    # Right Button (Portable)
    FlatBtn(
        btn_frame, text="No, Keep Portable", font=config.UI_FONT_BOLD,
        fg=config.COLOR_PANEL, bg=config.COLOR_ACCENT, active_bg="#1D4ED8",
        cmd=lambda: _set_choice(False), pad_x=16, pad_y=6
    ).pack(side="left") 

    # Pause execution until the dialog is closed
    parent.wait_window(dlg)

    return result["choice"]