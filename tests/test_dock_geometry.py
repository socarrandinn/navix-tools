import pytest

from dock.geometry import BAR, bar_height, bar_rect, expanded_rect, snap

AREA = (0, 0, 1920, 1040)


def test_bar_height_grows_with_tools():
    assert bar_height(1) < bar_height(3)
    assert bar_height(1) <= 70


def test_bar_right_middle():
    assert bar_rect(AREA, "right", 0.5, 60) == (1868, 490, BAR, 60)


def test_bar_left_top_and_bottom():
    assert bar_rect(AREA, "left", 0.0, 60) == (12, 12, BAR, 60)
    assert bar_rect(AREA, "left", 1.0, 60) == (12, 968, BAR, 60)


def test_expanded_keeps_bar_top_and_grows_inward():
    assert expanded_rect(AREA, "right", 0.5, 60, 320, 200) == (1548, 490, 360, 200)
    assert expanded_rect(AREA, "left", 0.5, 60, 320, 200) == (12, 490, 360, 200)


def test_expanded_never_shorter_than_bar():
    assert expanded_rect(AREA, "right", 0.5, 60, 320, 10)[3] == 60


def test_expanded_clamped_inside_area():
    assert expanded_rect(AREA, "right", 1.0, 60, 320, 400)[1] == 1040 - 12 - 400
    x, y, w, h = expanded_rect((0, 0, 1280, 300), "right", 0.5, 60, 320, 400)
    assert (y, h) == (12, 276)


def test_snap_to_nearest_edge_and_position():
    assert snap(AREA, 100, 490, 60) == ("left", 0.5)
    assert snap(AREA, 1800, 12, 60) == ("right", 0.0)


def test_snap_clamps_position():
    assert snap(AREA, 1800, -500, 60) == ("right", 0.0)
    assert snap(AREA, 1800, 5000, 60) == ("right", 1.0)


@pytest.mark.parametrize("area", [AREA, (-1920, 0, 1920, 1080), (1920, 40, 2560, 1400)])
@pytest.mark.parametrize("edge", ["left", "right"])
@pytest.mark.parametrize("position", [0.0, 0.5, 1.0])
def test_bar_and_expanded_stay_inside_area(area, edge, position):
    ax, ay, aw, ah = area
    for x, y, w, h in (bar_rect(area, edge, position, 60), expanded_rect(area, edge, position, 60, 320, 420)):
        assert ax <= x and x + w <= ax + aw
        assert ay <= y and y + h <= ay + ah
