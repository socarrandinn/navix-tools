from __future__ import annotations

import ctypes
from ctypes import wintypes

DWMWA_USE_IMMERSIVE_DARK_MODE = 20
DWMWA_WINDOW_CORNER_PREFERENCE = 33
DWMWA_SYSTEMBACKDROP_TYPE = 38
DWMWCP_ROUND = 2
DWMSBT_NONE = 1
DWMSBT_TRANSIENTWINDOW = 3  # acrylic


class MARGINS(ctypes.Structure):
    _fields_ = [("left", ctypes.c_int), ("right", ctypes.c_int), ("top", ctypes.c_int), ("bottom", ctypes.c_int)]


def _set_attribute(dwm, hwnd: int, attribute: int, value: int) -> int:
    data = ctypes.c_int(value)
    return dwm.DwmSetWindowAttribute(wintypes.HWND(hwnd), attribute, ctypes.byref(data), ctypes.sizeof(data))


def apply_backdrop(hwnd: int, enabled: bool = True) -> bool:
    """Activa (o apaga) acrylic + esquinas redondeadas (Win11 22H2+). False si DWM lo rechaza.

    El backdrop de DWM cubre el rectángulo completo de la ventana, por eso se apaga mientras
    el panel es un círculo.
    """
    if not hwnd:
        return False
    try:
        dwm = ctypes.windll.dwmapi
    except (AttributeError, OSError):
        return False
    margins = MARGINS(-1, -1, -1, -1)
    if dwm.DwmExtendFrameIntoClientArea(wintypes.HWND(hwnd), ctypes.byref(margins)) != 0:
        return False
    _set_attribute(dwm, hwnd, DWMWA_USE_IMMERSIVE_DARK_MODE, 1)
    _set_attribute(dwm, hwnd, DWMWA_WINDOW_CORNER_PREFERENCE, DWMWCP_ROUND)
    kind = DWMSBT_TRANSIENTWINDOW if enabled else DWMSBT_NONE
    return _set_attribute(dwm, hwnd, DWMWA_SYSTEMBACKDROP_TYPE, kind) == 0
