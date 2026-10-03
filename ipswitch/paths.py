"""Carpetas de Windows resueltas con SHGetKnownFolderPath.

No se usan variables de entorno (ProgramData, LOCALAPPDATA, ProgramFiles): un proceso sin
privilegios puede cambiarlas en HKCU\\Environment y la tarea elevada las heredaría.
"""

from __future__ import annotations

import ctypes
import uuid
from ctypes import wintypes
from pathlib import Path

FOLDERID_PROGRAM_DATA = "62AB5D82-FDC1-4DC3-A9DD-070D1D495D97"
FOLDERID_LOCAL_APP_DATA = "F1B32785-6FBA-4FCF-9D55-7B8E7F157091"
FOLDERID_PROGRAM_FILES = "905E63B6-C1BF-494E-B29C-65B732D3D21A"


class _GUID(ctypes.Structure):
    _fields_ = [
        ("Data1", wintypes.DWORD),
        ("Data2", wintypes.WORD),
        ("Data3", wintypes.WORD),
        ("Data4", ctypes.c_ubyte * 8),
    ]


def known_folder(folder_id: str) -> Path:
    value = uuid.UUID(folder_id)
    guid = _GUID(value.fields[0], value.fields[1], value.fields[2], (ctypes.c_ubyte * 8)(*value.bytes[8:]))
    path = ctypes.c_wchar_p()
    result = ctypes.windll.shell32.SHGetKnownFolderPath(ctypes.byref(guid), 0, None, ctypes.byref(path))
    try:
        if result != 0:
            raise OSError(f"SHGetKnownFolderPath falló ({result & 0xFFFFFFFF:#010x})")
        return Path(path.value)
    finally:
        ctypes.windll.ole32.CoTaskMemFree(path)
