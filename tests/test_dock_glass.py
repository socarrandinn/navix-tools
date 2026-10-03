import pytest
from PySide6.QtCore import QPointF
from PySide6.QtGui import QColor, QImage, QPainter

from dock.glass import droplet_path, paint_glass

F = 8


def inside(path, x, y):
    return path.contains(QPointF(x, y))


def test_right_droplet_flares_onto_the_screen_edge(qapp):
    path = droplet_path(40, 100, "right", radius=20, flare=F)
    assert inside(path, 20, 50)
    assert inside(path, 40 - 0.5, F - 1)          # se derrama sobre el borde, arriba
    assert inside(path, 40 - 0.5, 100 - F + 1)    # y abajo
    assert not inside(path, 0.5, F - 1)           # lado libre: no toca la esquina
    assert not inside(path, 1, F + 1)             # extremo libre redondeado


def test_left_droplet_is_mirrored(qapp):
    path = droplet_path(40, 100, "left", radius=20, flare=F)
    assert inside(path, 0.5, F - 1)
    assert not inside(path, 40 - 0.5, F - 1)
    assert not inside(path, 39, F + 1)


def test_top_droplet_hangs_from_the_top_edge(qapp):
    path = droplet_path(100, 40, "top", radius=20, flare=F)
    assert inside(path, 50, 20)
    assert inside(path, F - 1, 0.5)
    assert not inside(path, F - 1, 40 - 0.5)
    assert not inside(path, F + 1, 39)


@pytest.mark.parametrize("backdrop", [True, False])
def test_paint_glass_fills_only_the_droplet(qapp, backdrop):
    image = QImage(40, 100, QImage.Format.Format_ARGB32_Premultiplied)
    image.fill(QColor(0, 0, 0, 0))
    painter = QPainter(image)
    path = droplet_path(40, 100, "right", radius=20, flare=F)
    paint_glass(painter, path, backdrop)
    painter.end()
    assert QColor(image.pixel(20, 50)).alpha() > 0
    assert image.pixelColor(1, 2).alpha() == 0
