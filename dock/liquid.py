"""Forma de gota líquida del panel y su pintura sólida.

La gota se arma en coordenadas de borde derecho (grosor T hacia la izquierda, largo L hacia abajo):
el extremo libre es redondeado y el lado pegado a la pantalla se "derrama" con dos curvas
cóncavas. Con ``wobble`` el lado libre ondula como un líquido (el lado de la pantalla queda fijo).
Con ``bump`` el lado libre se hincha hacia afuera alrededor de ``bump_at`` (ícono bajo el mouse).
Para el borde izquierdo se espeja y para el superior se rota.
"""

from __future__ import annotations

import math

from PySide6.QtCore import QPointF, QRectF
from PySide6.QtGui import QColor, QLinearGradient, QPainter, QPainterPath, QPen, QPolygonF, QTransform

SAMPLES = 220
NECK_MAX = 30  # ancho máximo de la unión entre dos gotas, en px
WAVES = 1.5  # ondas a lo largo de la gota
BUMP_SIGMA = 20.0  # ancho (px) del bulto que hincha la barra bajo el ícono


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


def _ripple(path: QPainterPath, thickness: float, length: float, wobble: float, phase: float,
            bump: float = 0.0, bump_at: float = 0.0) -> QPainterPath:
    points = []
    for index in range(SAMPLES):
        point = path.pointAtPercent(index / SAMPLES)
        weight = max(0.0, 1.0 - point.x() / thickness)  # 1 en el lado libre, 0 pegado a la pantalla
        wave = math.sin(phase + 2 * math.pi * WAVES * point.y() / max(1.0, length))
        swell = bump * math.exp(-((point.y() - bump_at) / BUMP_SIGMA) ** 2)
        x = min(thickness, max(-bump, point.x() + (wobble * wave - swell) * weight))
        points.append(QPointF(x, point.y()))
    rippled = QPainterPath()
    rippled.addPolygon(QPolygonF(points))
    rippled.closeSubpath()
    return rippled


def droplet_path(width: float, height: float, edge: str, radius: float, flare: float,
                 wobble: float = 0.0, phase: float = 0.0, bump: float = 0.0,
                 bump_at: float = 0.0) -> QPainterPath:
    """``bump_at`` se mide a lo largo de la barra (y en bordes laterales, x en el superior)."""
    thickness, length = (height, width) if edge == "top" else (width, height)
    path = _right_droplet(thickness, length, radius, flare)
    if wobble or bump:
        path = _ripple(path, thickness, length, wobble, phase, bump, bump_at)
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


def bridge_path(a: QRectF, b: QRectF, horizontal: bool, thickness: float) -> QPainterPath:
    """Cuello líquido entre dos gotas enfrentadas, como un menisco. Vacío si ya se cortó.

    El borde sale tangente a la pared de cada gota (sin esquinas) y se curva hasta el punto más
    fino en el medio, así las gotas parecen fundirse. La unión con cada gota mide como mucho NECK_MAX.
    horizontal=True: gotas una al lado de la otra (bordes izquierdo/derecho); False: una arriba de otra.
    """
    path = QPainterPath()
    if thickness <= 0.5:
        return path
    if horizontal:
        first, second = (a, b) if a.center().x() <= b.center().x() else (b, a)
        low, high = max(first.top(), second.top()), min(first.bottom(), second.bottom())
        wall1, wall2 = first.right(), second.left()
    else:
        first, second = (a, b) if a.center().y() <= b.center().y() else (b, a)
        low, high = max(first.left(), second.left()), min(first.right(), second.right())
        wall1, wall2 = first.bottom(), second.top()
    if high <= low or wall2 <= wall1:
        return path
    center = (low + high) / 2
    attach = min((high - low) / 2, NECK_MAX / 2)
    mid = min(thickness / 2, attach - 4)
    middle = (wall1 + wall2) / 2
    reach = (wall2 - wall1) / 4

    # Contorno en coordenadas (u a lo largo del hueco, v a lo ancho); luego se vuelca al eje real.
    outline = [("move", (wall1 - 2, center - attach)), ("line", (wall1, center - attach)),
               ("cubic", (wall1, center - mid), (middle - reach, center - mid), (middle, center - mid)),
               ("cubic", (middle + reach, center - mid), (wall2, center - mid), (wall2, center - attach)),
               ("line", (wall2 + 2, center - attach)), ("line", (wall2 + 2, center + attach)),
               ("line", (wall2, center + attach)),
               ("cubic", (wall2, center + mid), (middle + reach, center + mid), (middle, center + mid)),
               ("cubic", (middle - reach, center + mid), (wall1, center + mid), (wall1, center + attach)),
               ("line", (wall1 - 2, center + attach))]

    def point(uv):
        u, v = uv
        return QPointF(u, v) if horizontal else QPointF(v, u)

    for kind, *coords in outline:
        points = [point(c) for c in coords]
        if kind == "move":
            path.moveTo(points[0])
        elif kind == "line":
            path.lineTo(points[0])
        else:
            path.cubicTo(*points)
    path.closeSubpath()
    return path
