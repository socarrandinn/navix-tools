"""Forma de gota y material "vidrio líquido" del panel.

La gota se arma en coordenadas de borde derecho (grosor T hacia la izquierda, largo L hacia abajo):
el extremo libre es redondeado y el lado pegado a la pantalla se "derrama" con dos curvas
cóncavas. Para el borde izquierdo se espeja y para el superior se rota.
"""

from __future__ import annotations

from PySide6.QtCore import QPointF, QRectF, Qt
from PySide6.QtGui import QBrush, QColor, QLinearGradient, QPainter, QPainterPath, QPen, QRadialGradient, QTransform


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


def droplet_path(width: float, height: float, edge: str, radius: float, flare: float) -> QPainterPath:
    if edge == "top":
        path = _right_droplet(height, width, radius, flare)
        # (x, y) del borde derecho -> (y, T - x) del borde superior
        return QTransform(0, -1, 1, 0, 0, height).map(path)
    path = _right_droplet(width, height, radius, flare)
    if edge == "left":
        return QTransform(-1, 0, 0, 1, width, 0).map(path)
    return path


def paint_glass(painter: QPainter, path: QPainterPath, backdrop_active: bool) -> None:
    """Tinte translúcido + reflejo superior + brillo interior + borde especular."""
    painter.save()
    painter.setRenderHint(QPainter.RenderHint.Antialiasing)
    rect = path.boundingRect()

    base = QLinearGradient(rect.topLeft(), rect.bottomLeft())
    if backdrop_active:
        base.setColorAt(0.0, QColor(255, 255, 255, 46))
        base.setColorAt(1.0, QColor(255, 255, 255, 12))
    else:
        base.setColorAt(0.0, QColor(56, 62, 76, 232))
        base.setColorAt(1.0, QColor(22, 24, 32, 236))
    painter.fillPath(path, base)

    painter.setClipPath(path)
    sheen = QRadialGradient(QPointF(rect.center().x(), rect.top()), max(rect.width(), rect.height()) * 0.7)
    sheen.setColorAt(0.0, QColor(255, 255, 255, 72))
    sheen.setColorAt(1.0, QColor(255, 255, 255, 0))
    painter.fillRect(QRectF(rect.left(), rect.top(), rect.width(), rect.height() * 0.55), sheen)
    glow = QLinearGradient(QPointF(0, rect.bottom() - rect.height() * 0.3), QPointF(0, rect.bottom()))
    glow.setColorAt(0.0, QColor(255, 255, 255, 0))
    glow.setColorAt(1.0, QColor(255, 255, 255, 26))
    painter.fillRect(rect, glow)
    painter.setClipping(False)

    rim = QLinearGradient(rect.topLeft(), rect.bottomRight())
    rim.setColorAt(0.0, QColor(255, 255, 255, 200))
    rim.setColorAt(0.45, QColor(255, 255, 255, 36))
    rim.setColorAt(1.0, QColor(255, 255, 255, 120))
    painter.setPen(QPen(QBrush(rim), 1.2))
    painter.setBrush(Qt.BrushStyle.NoBrush)
    painter.drawPath(path)
    painter.restore()
