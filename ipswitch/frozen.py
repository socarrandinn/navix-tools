"""Rutas de la app instalada (PyInstaller): C:\Program Files\IPDock\IPDock.exe y cli\ipswitch.exe."""

from __future__ import annotations

import sys
from pathlib import Path

DOCK_EXE = "IPDock.exe"
CLI_EXE = "ipswitch.exe"


def is_frozen() -> bool:
    return bool(getattr(sys, "frozen", False))


def app_dir(executable: str | Path) -> Path:
    path = Path(executable)
    return path.parent.parent if path.name.lower() == CLI_EXE.lower() else path.parent


def dock_exe(executable: str | Path) -> Path:
    return app_dir(executable) / DOCK_EXE


def cli_exe(executable: str | Path) -> Path:
    return app_dir(executable) / "cli" / CLI_EXE
