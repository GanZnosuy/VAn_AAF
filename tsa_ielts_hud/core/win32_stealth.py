"""Native Windows ctypes: WS_EX_TRANSPARENT click-through & WDA_EXCLUDEFROMCAPTURE screen-capture stealth."""

from __future__ import annotations

import ctypes
import logging
import sys
from typing import Optional

logger = logging.getLogger(__name__)

# Win32 Extended Window Style Constants
GWL_EXSTYLE: int = -20
WS_EX_LAYERED: int = 0x00080000
WS_EX_TRANSPARENT: int = 0x00000020  # Click-through flag

# Win32 Display Affinity Constants
WDA_NONE: int = 0x00000000
WDA_MONITOR: int = 0x00000001
WDA_EXCLUDEFROMCAPTURE: int = 0x00000011  # Windows 10 build 19041+ stealth


def _get_user32():
    """Safely retrieves user32 DLL on Windows systems."""
    if sys.platform != "win32":
        return None
    try:
        return ctypes.windll.user32
    except Exception as e:
        logger.warning("Could not access user32.dll: %s", e)
        return None


def set_window_stealth_and_clickthrough(
    hwnd: int,
    click_through: bool = True,
    hide_from_capture: bool = True,
) -> bool:
    """
    Configures HWND for:
    1. Click-through: toggles WS_EX_TRANSPARENT layered attribute.
    2. Stealth: calls SetWindowDisplayAffinity(WDA_EXCLUDEFROMCAPTURE) to hide from
       screen-capture tools (OBS, Zoom, print-screen, MSS) while remaining visible to the user.

    Returns True if operations succeeded, False otherwise.
    """
    if sys.platform != "win32":
        logger.debug("Non-Windows OS detected; win32 stealth skipped.")
        return False

    if not hwnd:
        logger.warning("Invalid HWND provided to set_window_stealth_and_clickthrough.")
        return False

    user32 = _get_user32()
    if not user32:
        return False

    success = True

    # 1. Click-through & Layered Style Setup
    try:
        # Determine 64-bit vs 32-bit Get/SetWindowLong
        if hasattr(user32, "GetWindowLongPtrW"):
            get_window_long = user32.GetWindowLongPtrW
            set_window_long = user32.SetWindowLongPtrW
            get_window_long.argtypes = [ctypes.c_void_p, ctypes.c_int]
            get_window_long.restype = ctypes.c_void_p
            set_window_long.argtypes = [ctypes.c_void_p, ctypes.c_int, ctypes.c_void_p]
            set_window_long.restype = ctypes.c_void_p
        else:
            get_window_long = user32.GetWindowLongW
            set_window_long = user32.SetWindowLongW
            get_window_long.argtypes = [ctypes.c_void_p, ctypes.c_int]
            get_window_long.restype = ctypes.c_long
            set_window_long.argtypes = [ctypes.c_void_p, ctypes.c_int, ctypes.c_long]
            set_window_long.restype = ctypes.c_long

        cur_style = int(get_window_long(ctypes.c_void_p(hwnd), GWL_EXSTYLE))

        if click_through:
            # Enable layered and transparent (click-through)
            new_style = cur_style | WS_EX_LAYERED | WS_EX_TRANSPARENT
        else:
            # Layered kept for alpha transparency, but click-through removed so user can click/type
            new_style = (cur_style | WS_EX_LAYERED) & ~WS_EX_TRANSPARENT

        if new_style != cur_style:
            res = set_window_long(ctypes.c_void_p(hwnd), GWL_EXSTYLE, new_style)
            if res == 0 and ctypes.get_last_error() != 0:
                logger.warning("Failed to set window style. Last error: %s", ctypes.get_last_error())
                success = False

    except Exception as e:
        logger.error("Exception setting click-through style on hwnd %s: %s", hwnd, e)
        success = False

    # 2. SetWindowDisplayAffinity for Screen-Capture Stealth
    try:
        if hasattr(user32, "SetWindowDisplayAffinity"):
            set_affinity = user32.SetWindowDisplayAffinity
            set_affinity.argtypes = [ctypes.c_void_p, ctypes.c_uint32]
            set_affinity.restype = ctypes.c_bool

            affinity = WDA_EXCLUDEFROMCAPTURE if hide_from_capture else WDA_NONE
            aff_res = set_affinity(ctypes.c_void_p(hwnd), affinity)
            if not aff_res:
                logger.warning(
                    "SetWindowDisplayAffinity(%s) returned False for hwnd %s. Last error: %s",
                    affinity,
                    hwnd,
                    ctypes.get_last_error(),
                )
                # Some Windows builds don't support WDA_EXCLUDEFROMCAPTURE (0x11), fallback to WDA_MONITOR (0x01)
                if hide_from_capture:
                    fallback_res = set_affinity(ctypes.c_void_p(hwnd), WDA_MONITOR)
                    if not fallback_res:
                        success = False
            else:
                logger.debug("Successfully applied display affinity %s to hwnd %s", affinity, hwnd)
        else:
            logger.warning("SetWindowDisplayAffinity not available in user32")
            success = False
    except Exception as e:
        logger.error("Exception calling SetWindowDisplayAffinity on hwnd %s: %s", hwnd, e)
        success = False

    return success
