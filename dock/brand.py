"""Nombre de la app y carpetas de datos. Antes se llamaba IPDock: su carpeta se mueve sola."""

from __future__ import annotations

import shutil
from pathlib import Path

APP_NAME = "Navix Tools"
APP_SLUG = "navix"
LEGACY_SLUG = "ipdock"


def data_folder(base: Path) -> Path:
    """``base/navix``; si solo existe la carpeta vieja ``base/ipdock``, la mueve (o copia) ahí."""
    folder, legacy = base / APP_SLUG, base / LEGACY_SLUG
    if not folder.exists() and legacy.is_dir():
        try:
            legacy.rename(folder)
        except OSError:
            shutil.copytree(legacy, folder, dirs_exist_ok=True)
    return folder
