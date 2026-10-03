import pytest

from dock.geometry import panel_rect

AREA = (0, 0, 1920, 1040)


def test_right_revealed():
    assert panel_rect(AREA, "right", 320, True) == (1588, 12, 320, 1016)


def test_right_hidden_is_handle_strip():
    assert panel_rect(AREA, "right", 320, False) == (1914, 12, 6, 1016)


def test_left_revealed_and_hidden():
    assert panel_rect(AREA, "left", 320, True) == (12, 12, 320, 1016)
    assert panel_rect(AREA, "left", 320, False) == (0, 12, 6, 1016)


@pytest.mark.parametrize("area", [AREA, (-1920, 0, 1920, 1080), (1920, 40, 2560, 1400)])
@pytest.mark.parametrize("edge", ["left", "right"])
def test_hidden_rect_stays_inside_area(area, edge):
    ax, ay, aw, ah = area
    x, y, w, h = panel_rect(area, edge, 320, False)
    assert ax <= x and x + w <= ax + aw
    assert ay <= y and y + h <= ay + ah
