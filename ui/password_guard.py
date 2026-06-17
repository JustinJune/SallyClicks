# ui/password_guard.py
#
# Detects whether the currently focused UI element in another app is a
# password / secure text field, and warns the user before recording starts.
#
import sys


def focused_element_is_password() -> bool:
    """
    Returns True if the OS reports that the currently focused field
    in the frontmost application is a secure / password input.
    Fails silently and returns False if the check can't be performed.
    """
    if sys.platform != "darwin":
        return False

    try:
        # Use macOS Accessibility API via pyobjc
        from ApplicationServices import (
            AXUIElementCreateSystemWide,
            AXUIElementCopyAttributeValue,
            kAXFocusedUIElementAttribute,
            kAXRoleAttribute,
            kAXSubroleAttribute,
        )
        system = AXUIElementCreateSystemWide()

        err, focused = AXUIElementCopyAttributeValue(
            system, kAXFocusedUIElementAttribute, None
        )
        if err != 0 or focused is None:
            return False

        # Check role: AXTextField with AXSecureTextField subrole = password field
        err_r, role = AXUIElementCopyAttributeValue(focused, kAXRoleAttribute, None)
        err_s, subrole = AXUIElementCopyAttributeValue(focused, kAXSubroleAttribute, None)

        role_str    = str(role)    if err_r == 0 else ""
        subrole_str = str(subrole) if err_s == 0 else ""

        return "SecureTextField" in role_str or "AXSecureTextField" in subrole_str

    except Exception:
        # pyobjc not available, or AX query failed — don't block the user
        return False


def warn_if_password_focused(parent_widget) -> bool:
    """
    Shows a warning dialog if a password field is detected.
    Returns True if the user still wants to proceed, False to abort.
    """
    if not focused_element_is_password():
        return True   # no issue detected, proceed

    from tkinter import messagebox
    proceed = messagebox.askyesno(
        "⚠️  Password Field Detected",
        "The currently focused field appears to be a password input.\n\n"
        "Recording now will capture your keystrokes — including your password.\n\n"
        "Are you sure you want to start recording?",
        icon="warning",
        parent=parent_widget,
        default="no",
    )
    return proceed