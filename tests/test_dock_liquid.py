import pytest
from PySide6.QtCore import QPointF
from PySide6.QtGui import QColor, QImage, QPainter

from PySide6.QtCore import QRectF

from dock.liquid import bridge_path, droplet_path, paint_liquid

F = 8


def inside(path, x, y):
    return path.contains(QPointF(x, y))


def test_right_droplet_flares_onto_the_screen_edge(qapp):
    path = droplet_path(40, 100, "right", radius=20, flare=F)
    assert inside(path, 20, 50)
    assert inside(path, 40 - 0.5, F - 1)
    assert inside(path, 40 - 0.5, 100 - F + 1)
    assert not inside(path, 0.5, F - 1)
    assert not inside(path, 1, F + 1)


def test_left_droplet_is_mirrored(qapp):
    path = droplet_path(40, 100, "left", radius=20, flare=F)
    assert inside(path, 0.5, F - 1)
    assert not inside(path, 40 - 0.5, F - 1)


def test_top_droplet_hangs_from_the_top_edge(qapp):
    path = droplet_path(100, 40, "top", radius=20, flare=F)
    assert inside(path, 50, 20)
    assert inside(path, F - 1, 0.5)
    assert not inside(path, F - 1, 40 - 0.5)


def test_wobble_ripples_the_free_side_but_not_the_screen_edge(qapp):
    calm = droplet_path(200, 300, "right", radius=22, flare=F)
    wavy = droplet_path(200, 300, "right", radius=22, flare=F, wobble=6, phase=0.0)
    # en el lado libre (x chico) la onda mete y saca material
    changed = [y for y in range(40, 260, 5) if inside(calm, 3, y) != inside(wavy, 3, y)]
    assert changed
    # el lado pegado a la pantalla no se mueve
    assert all(inside(wavy, 199.5, y) for y in range(F + 2, 300 - F - 2, 10))


def test_wobble_stays_inside_the_window(qapp):
    wavy = droplet_path(200, 300, "right", radius=22, flare=F, wobble=6, phase=1.3)
    box = wavy.boundingRect()
    assert box.left() >= 0 and box.top() >= 0 and box.right() <= 200 and box.bottom() <= 300


def test_paint_liquid_is_solid_and_dark_inside_only(qapp):
    image = QImage(40, 100, QImage.Format.Format_ARGB32_Premultiplied)
    image.fill(QColor(0, 0, 0, 0))
    painter = QPainter(image)
    paint_liquid(painter, droplet_path(40, 100, "right", radius=20, flare=F))
    painter.end()
    center = image.pixelColor(20, 50)
    assert center.alpha() >= 240
    assert center.lightness() < 70
    assert image.pixelColor(1, 2).alpha() == 0


def test_bridge_connects_side_by_side_drops(qapp):
    left, right = QRectF(0, 0, 100, 200), QRectF(112, 60, 40, 80)
    neck = bridge_path(left, right, horizontal=True, thickness=30)
    assert inside(neck, 106, 100)
    assert not inside(neck, 106, 40)


def test_thin_bridge_has_broken(qapp):
    left, right = QRectF(0, 0, 100, 200), QRectF(112, 60, 40, 80)
    assert bridge_path(left, right, horizontal=True, thickness=0).isEmpty()


def test_vertical_bridge_for_top_edge(qapp):
    top, bottom = QRectF(60, 0, 80, 40), QRectF(0, 52, 200, 100)
    neck = bridge_path(top, bottom, horizontal=False, thickness=30)
    assert inside(neck, 100, 46)
    assert not inside(neck, 20, 46)
