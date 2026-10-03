from PySide6.QtCore import QSize

from dock.icons import has_icon, svg_icon


def test_bundled_lucide_icons_exist():
    for name in ("network", "gauge", "pin", "x"):
        assert has_icon(name), name


def test_unknown_names_are_not_icons():
    assert not has_icon("C")
    assert not has_icon("../secret")
    assert svg_icon("no-existe") is None


def test_svg_icon_renders_in_requested_color(qapp):
    icon = svg_icon("network", color="#ff0000", size=18)
    image = icon.pixmap(QSize(18, 18)).toImage()
    colored = [
        image.pixelColor(x, y)
        for x in range(image.width())
        for y in range(image.height())
        if image.pixelColor(x, y).alpha() > 200
    ]
    assert colored
    assert all(c.red() > 200 and c.green() < 60 and c.blue() < 60 for c in colored)
