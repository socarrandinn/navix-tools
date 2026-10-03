"""Forma de gota líquida del panel y su pintura sólida.

La gota se arma en coordenadas de borde derecho (grosor T hacia la izquierda, largo L hacia abajo):
el extremo libre es redondeado y el lado pegado a la pantalla se "derrama" con dos curvas
cóncavas. Con ``wobble`` el lado libre ondula como un líquido (el lado de la pantalla queda fijo).
Para el borde izquierdo se espeja y para el superior se rota.
"""

from __future__ import annotations

import math

from PySide6.QtCore import QPointF, QRectF
from PySide6.QtGui import QColor, QLinearGradient, QPainter, QPainterPath, QPen, QPolygonF, QTransform

SAMPLES = 220
WAVES = 1.5  # ondas a lo largo de la gota


def _right_droplet(thickness: float, length: float, radius: float, flare: float) -> QPainterPath:
    body_height = max(1.0, length - 2 * flare)
    radius = max(0.0, min(radius, body_height / 2, thickness))
    body = QPainterPath()
    body.addRoundedRect(QRectF(0, flare, thickness, body_height), radius, radius)
    square = QPainterPath()
    square.addRect(QRectF(thickness - radius, flare, radius, body_height))
    shape = body.united(square)
    for corner_y, circle_y in ((0.0, 0.0), (length - flare, length)):
        fillet = QPainterPath()
        fillet.addRect(QRectF(thickness - flare, corner_y, flare, flare))
        circle = QPainterPath()
        circle.addEllipse(QPointF(thickness - flare, circle_y), flare, flare)
        shape = shape.united(fillet.subtracted(circle))
    return shape.simplified()


def _ripple(path: QPainterPath, thickness: float, length: float, wobble: float, phase: float) -> QPainterPath:
    points = []
    for index in range(SAMPLES):
        point = path.pointAtPercent(index / SAMPLES)
        weight = max(0.0, 1.0 - point.x() / thickness)  # 1 en el lado libre, 0 pegado a la pantalla
        wave = math.sin(phase + 2 * math.pi * WAVES * point.y() / max(1.0, length))
        x = min(thickness, max(0.0, point.x() + wobble * weight * wave))
        points.append(QPointF(x, point.y()))
    rippled = QPainterPath()
    rippled.addPolygon(QPolygonF(points))
    rippled.closeSubpath()
    return rippled


def droplet_path(width: float, height: float, edge: str, radius: float, flare: float,
                 wobble: float = 0.0, phase: float = 0.0) -> QPainterPath:
    thickness, length = (height, width) if edge == "top" else (width, height)
    path = _right_droplet(thickness, length, radius, flare)
    if wobble:
        path = _ripple(path, thickness, length, wobble, phase)
    if edge == "top":
        # (x, y) del borde derecho -> (y, T - x) del borde superior
        return QTransform(0, -1, 1, 0, 0, height).map(path)
    if edge == "left":
        return QTransform(-1, 0, 0, 1, width, 0).map(path)
    return path


def paint_liquid(painter: QPainter, path: QPainterPath) -> None:
    """Relleno sólido oscuro con un brillo suave arriba, como una gota de tinta."""
    painter.save()
    painter.setRenderHint(QPainter.RenderHint.Antialiasing)
    rect = path.boundingRect()
    fill = QLinearGradient(rect.topLeft(), rect.bottomLeft())
    fill.setColorAt(0.0, QColor(38, 43, 56, 250))
    fill.setColorAt(1.0, QColor(18, 20, 27, 250))
    painter.fillPath(path, fill)
    painter.setClipPath(path)
    shine = QLinearGradient(rect.topLeft(), QPointF(rect.left(), rect.top() + min(60.0, rect.height() * 0.4)))
    shine.setColorAt(0.0, QColor(255, 255, 255, 22))
    shine.setColorAt(1.0, QColor(255, 255, 255, 0))
    painter.fillRect(rect, shine)
    painter.setClipping(False)
    painter.setPen(QPen(QColor(255, 255, 255, 18), 1))
    painter.drawPath(path)
    painter.restore()
