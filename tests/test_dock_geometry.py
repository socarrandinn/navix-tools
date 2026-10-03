import pytest

from dock.geometry import BUBBLE, bubble_rect, expanded_rect, snap

AREA = (0, 0, 1920, 1040)


def test_bubble_right_middle():
    assert bubble_rect(AREA, "right", 0.5) == (1858, 495, BUBBLE, BUBBLE)


def test_bubble_left_top_and_bottom():
    assert bubble_rect(AREA, "left", 0.0) == (12, 12, BUBBLE, BUBBLE)
    assert bubble_rect(AREA, "left", 1.0) == (12, 978, BUBBLE, BUBBLE)


def test_expanded_anchored_to_edge_and_centered_on_bubble():
    assert expanded_rect(AREA, "right", 320, 0.5, height=400) == (1588, 320, 320, 400)
    assert expanded_rect(AREA, "left", 320, 0.5, height=400) == (12, 320, 320, 400)


def test_expanded_clamped_inside_area():
    assert expanded_rect(AREA, "right", 320, 0.0, height=400)[1] == 12
    assert expanded_rect(AREA, "right", 320, 1.0, height=400)[1] == 1040 - 12 - 400


def test_expanded_height_never_exceeds_area():
    x, y, w, h = expanded_rect((0, 0, 1280, 300), "right", 320, 0.5, height=400)
    assert (y, h) == (12, 276)


def test_snap_to_nearest_edge_and_position():
    assert snap(AREA, 100, 495) == ("left", 0.5)
    assert snap(AREA, 1800, 12) == ("right", 0.0)


def test_snap_clamps_position():
    assert snap(AREA, 1800, -500) == ("right", 0.0)
    assert snap(AREA, 1800, 5000) == ("right", 1.0)


@pytest.mark.parametrize("area", [AREA, (-1920, 0, 1920, 1080), (1920, 40, 2560, 1400)])
@pytest.mark.parametrize("edge", ["left", "right"])
@pytest.mark.parametrize("position", [0.0, 0.5, 1.0])
def test_bubble_and_panel_stay_inside_area(area, edge, position):
    ax, ay, aw, ah = area
    for x, y, w, h in (bubble_rect(area, edge, position), expanded_rect(area, edge, 320, position)):
        assert ax <= x and x + w <= ax + aw
        assert ay <= y and y + h <= ay + ah
