"""Íconos SVG (Lucide, licencia ISC: assets/icons/LICENSE-lucide.txt) pintados en un color dado."""

from __future__ import annotations

import re
from functools import lru_cache
from pathlib import Path

from PySide6.QtCore import QByteArray, QRectF, QSize, Qt
from PySide6.QtGui import QGuiApplication, QIcon, QPainter, QPixmap
from PySide6.QtSvg import QSvgRenderer

ICON_DIR = Path(__file__).resolve().parent / "assets" / "icons"
NAME = re.compile(r"^[a-z0-9-]+$")


def has_icon(name: str) -> bool:
    return bool(NAME.match(name)) and (ICON_DIR / f"{name}.svg").is_file()


@lru_cache(maxsize=64)
def _svg(name: str, color: str) -> bytes:
    return (ICON_DIR / f"{name}.svg").read_text(encoding="utf-8").replace("currentColor", color).encode("utf-8")


def svg_icon(name: str, color: str = "#f0f4f8", size: int = 18) -> QIcon | None:
    if not has_icon(name):
        return None
    renderer = QSvgRenderer(QByteArray(_svg(name, color)))
    app = QGuiApplication.instance()
    ratio = app.devicePixelRatio() if app is not None else 1.0
    scale = max(2.0, ratio)  # renderizar al doble para que se vea nítido en pantallas con escala
    pixmap = QPixmap(QSize(round(size * scale), round(size * scale)))
    pixmap.fill(Qt.GlobalColor.transparent)
    painter = QPainter(pixmap)
    painter.setRenderHint(QPainter.RenderHint.Antialiasing)
    renderer.render(painter, QRectF(0, 0, pixmap.width(), pixmap.height()))
    painter.end()
    pixmap.setDevicePixelRatio(scale)
    return QIcon(pixmap)
