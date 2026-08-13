"""Low-level Windows mouse input via SendInput (user32).

Injects hardware-level mouse events through the Win32 SendInput API instead of
going through a high-level wrapper. Move + button-down + button-up are sent as a
single atomic input batch, and coordinates are given in true screen pixels so the
values map 1:1 to the pixel coordinates a vision model returns from a full-res
screenshot.

Import this module early (before any screenshot/coordinate work) so process DPI
awareness is set before the coordinate space is queried.

Windows only.
"""

from __future__ import annotations

import ctypes
import sys
from ctypes import wintypes
from enum import Enum

if sys.platform != "win32":
    raise RuntimeError("win_click only supports Windows (SendInput / user32).")

_user32 = ctypes.WinDLL("user32", use_last_error=True)

# ULONG_PTR is pointer-sized; getting this wrong silently corrupts the struct on 64-bit.
ULONG_PTR = ctypes.c_ulonglong if ctypes.sizeof(ctypes.c_void_p) == 8 else ctypes.c_ulong

# --- MOUSEEVENTF flags -------------------------------------------------------
_MOVE = 0x0001
_ABSOLUTE = 0x8000
_VIRTUALDESK = 0x4000
_BUTTON_FLAGS = {
    "left": (0x0002, 0x0004),    # down, up
    "right": (0x0008, 0x0010),
    "middle": (0x0020, 0x0040),
}

# --- GetSystemMetrics indices for the virtual (multi-monitor) desktop --------
_SM_XVIRTUALSCREEN = 76
_SM_YVIRTUALSCREEN = 77
_SM_CXVIRTUALSCREEN = 78
_SM_CYVIRTUALSCREEN = 79

_INPUT_MOUSE = 0


class MouseButton(str, Enum):
    LEFT = "left"
    RIGHT = "right"
    MIDDLE = "middle"


class _MOUSEINPUT(ctypes.Structure):
    _fields_ = [
        ("dx", wintypes.LONG),
        ("dy", wintypes.LONG),
        ("mouseData", wintypes.DWORD),
        ("dwFlags", wintypes.DWORD),
        ("time", wintypes.DWORD),
        ("dwExtraInfo", ULONG_PTR),
    ]


class _INPUT(ctypes.Structure):
    class _U(ctypes.Union):
        _fields_ = [("mi", _MOUSEINPUT)]

    _anonymous_ = ("u",)
    _fields_ = [("type", wintypes.DWORD), ("u", _U)]


_user32.SendInput.argtypes = (wintypes.UINT, ctypes.POINTER(_INPUT), ctypes.c_int)
_user32.SendInput.restype = wintypes.UINT


def set_dpi_awareness() -> None:
    """Make this process per-monitor DPI aware.

    Without this, Windows silently scales coordinates on high-DPI displays, so a
    click aimed at a real pixel lands somewhere else. Best called once at startup.
    Tries newest API first, falls back for older Windows versions.
    """
    try:  # Windows 10 1703+  (PER_MONITOR_AWARE_V2 == -4)
        _user32.SetProcessDpiAwarenessContext(ctypes.c_void_p(-4))
        return
    except (AttributeError, OSError):
        pass
    try:  # Windows 8.1+  (PROCESS_PER_MONITOR_DPI_AWARE == 2)
        ctypes.WinDLL("shcore").SetProcessDpiAwareness(2)
        return
    except (AttributeError, OSError):
        pass
    try:  # Vista+ system-DPI fallback
        _user32.SetProcessDPIAware()
    except (AttributeError, OSError):
        pass


def _to_absolute(x: int, y: int) -> tuple[int, int]:
    """Map a real screen pixel to SendInput's 0..65535 virtual-desktop space."""
    vx = _user32.GetSystemMetrics(_SM_XVIRTUALSCREEN)
    vy = _user32.GetSystemMetrics(_SM_YVIRTUALSCREEN)
    vw = _user32.GetSystemMetrics(_SM_CXVIRTUALSCREEN)
    vh = _user32.GetSystemMetrics(_SM_CYVIRTUALSCREEN)
    abs_x = round((x - vx) * 65535 / (vw - 1))
    abs_y = round((y - vy) * 65535 / (vh - 1))
    return abs_x, abs_y


def _mouse_event(flags: int, abs_x: int = 0, abs_y: int = 0) -> _INPUT:
    return _INPUT(
        type=_INPUT_MOUSE,
        mi=_MOUSEINPUT(dx=abs_x, dy=abs_y, mouseData=0, dwFlags=flags, time=0, dwExtraInfo=0),
    )


def _send(events: list[_INPUT]) -> None:
    n = len(events)
    arr = (_INPUT * n)(*events)
    sent = _user32.SendInput(n, arr, ctypes.sizeof(_INPUT))
    if sent != n:
        raise ctypes.WinError(ctypes.get_last_error())


def click(x: int, y: int, button: MouseButton = MouseButton.LEFT) -> None:
    """Move to (x, y) in screen pixels and click, as one atomic input batch."""
    down, up = _BUTTON_FLAGS[MouseButton(button).value]
    abs_x, abs_y = _to_absolute(x, y)
    _send([
        _mouse_event(_MOVE | _ABSOLUTE | _VIRTUALDESK, abs_x, abs_y),
        _mouse_event(down),
        _mouse_event(up),
    ])


# Set DPI awareness on import so the coordinate space is correct from the start.
set_dpi_awareness()


if __name__ == "__main__":
    import time
    print("Clicking current cursor spot in 2s...")
    time.sleep(2)
    pt = wintypes.POINT()
    _user32.GetCursorPos(ctypes.byref(pt))
    click(pt.x, pt.y)
    print("done")