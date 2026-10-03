"""Guardar perfiles en el config solo-admin pidiendo UAC una vez por guardado.

Los perfiles viajan codificados en la línea de comando del proceso elevado (no en un archivo),
así ningún proceso sin privilegios puede cambiarlos mientras el diálogo UAC está abierto.
"""

from __future__ import annotations

import base64
import binascii
import ctypes
import json
import sys
from ctypes import wintypes
from pathlib import Path
from typing import Callable

from .config import AppConfig, ConfigError, config_to_dict, parse_config

PACKAGE_ROOT = str(Path(__file__).resolve().parent.parent)
ERROR_CANCELLED = 1223
Elevator = Callable[[str, str, str], int]


def encode_config(config: AppConfig) -> str:
    data = json.dumps(config_to_dict(config), ensure_ascii=False, separators=(",", ":")).encode("utf-8")
    return base64.urlsafe_b64encode(data).decode("ascii")


def decode_config(text: str) -> AppConfig:
    try:
        raw = json.loads(base64.urlsafe_b64decode(text.encode("ascii")).decode("utf-8"))
    except (ValueError, binascii.Error, UnicodeError) as exc:
        raise ConfigError(f"Configuración recibida ilegible: {exc}") from exc
    return parse_config(raw, "configuración recibida")


def save_config_command(config: AppConfig, executable: str = sys.executable) -> tuple[str, str, str]:
    pythonw = Path(executable).with_name("pythonw.exe")
    exe = str(pythonw) if pythonw.exists() else executable
    return exe, f"-m ipswitch save-config {encode_config(config)}", PACKAGE_ROOT


class _ShellExecuteInfo(ctypes.Structure):
    _fields_ = [
        ("cbSize", wintypes.DWORD), ("fMask", ctypes.c_ulong), ("hwnd", wintypes.HWND),
        ("lpVerb", wintypes.LPCWSTR), ("lpFile", wintypes.LPCWSTR), ("lpParameters", wintypes.LPCWSTR),
        ("lpDirectory", wintypes.LPCWSTR), ("nShow", ctypes.c_int), ("hInstApp", wintypes.HINSTANCE),
        ("lpIDList", ctypes.c_void_p), ("lpClass", wintypes.LPCWSTR), ("hkeyClass", wintypes.HKEY),
        ("dwHotKey", wintypes.DWORD), ("hIconOrMonitor", wintypes.HANDLE), ("hProcess", wintypes.HANDLE),
    ]


def run_elevated(executable: str, params: str, cwd: str) -> int:
    """Ejecuta con UAC y espera. Devuelve el código de salida, o -1 si el usuario canceló."""
    SEE_MASK_NOCLOSEPROCESS = 0x40
    info = _ShellExecuteInfo()
    info.cbSize = ctypes.sizeof(info)
    info.fMask = SEE_MASK_NOCLOSEPROCESS
    info.lpVerb, info.lpFile, info.lpParameters, info.lpDirectory = "runas", executable, params, cwd
    info.nShow = 0
    if not ctypes.windll.shell32.ShellExecuteExW(ctypes.byref(info)):
        if ctypes.GetLastError() == ERROR_CANCELLED:
            return -1
        raise ConfigError(f"No se pudo pedir permisos de administrador ({ctypes.GetLastError()})")
    kernel32 = ctypes.windll.kernel32
    kernel32.WaitForSingleObject(info.hProcess, 0xFFFFFFFF)
    code = wintypes.DWORD()
    kernel32.GetExitCodeProcess(info.hProcess, ctypes.byref(code))
    kernel32.CloseHandle(info.hProcess)
    return int(code.value)


def save_config_elevated(config: AppConfig, runner: Elevator = run_elevated) -> None:
    code = runner(*save_config_command(config))
    if code == -1:
        raise ConfigError("Guardado cancelado: se necesita permiso de administrador.")
    if code != 0:
        raise ConfigError(f"No se pudo guardar la configuración (código {code}).")
