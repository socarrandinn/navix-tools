import pytest

from dock.geometry import BAR, FLARE, bar_length, bar_rect, expanded_rect, snap

AREA = (0, 0, 1920, 1040)
L = 80


def test_bar_length_grows_with_tools_and_leaves_room_for_flares():
    assert bar_length(1) < bar_length(3)
    assert bar_length(1) <= 90
    assert bar_length(0) == bar_length(1)
    assert bar_length(1) > 2 * FLARE


def test_vertical_bars_touch_the_screen_edge():
    assert bar_rect(AREA, "right", 0.5, L) == (1920 - BAR, 480, BAR, L)
    assert bar_rect(AREA, "left", 0.0, L) == (0, 12, BAR, L)
    assert bar_rect(AREA, "left", 1.0, L) == (0, 1040 - 12 - L, BAR, L)


def test_top_bar_is_horizontal_and_touches_top():
    assert bar_rect(AREA, "top", 0.5, L) == (920, 0, L, BAR)
    assert bar_rect(AREA, "top", 0.0, L) == (12, 0, L, BAR)


def test_expanded_vertical_grows_inward_from_the_edge():
    assert expanded_rect(AREA, "right", 0.5, L, 320, 200) == (1920 - BAR - 320, 480, BAR + 320, 200)
    assert expanded_rect(AREA, "left", 0.5, L, 320, 200) == (0, 480, BAR + 320, 200)
    assert expanded_rect(AREA, "right", 0.5, L, 320, 10)[3] == L


def test_expanded_top_grows_down():
    assert expanded_rect(AREA, "top", 0.5, L, 320, 200) == (920, 0, 320, BAR + 200)
    assert expanded_rect(AREA, "top", 1.0, L, 320, 200)[0] == 1920 - 12 - 320


def test_expanded_clamped_inside_area():
    x, y, w, h = expanded_rect((0, 0, 1280, 300), "right", 0.5, L, 320, 400)
    assert (y, h) == (12, 276)
    x, y, w, h = expanded_rect((0, 0, 1280, 300), "top", 0.5, L, 320, 900)
    assert y + h <= 300


@pytest.mark.parametrize(
    "x, y, w, h, expected",
    [
        (1800, 480, BAR, L, ("right", 0.5)),
        (10, 12, BAR, L, ("left", 0.0)),
        (940, 30, BAR, L, ("top", 0.5)),
        (900, 5, L, BAR, ("top", 0.5)),
        (100, 500, L, BAR, ("left", 0.5)),
    ],
)
def test_snap_picks_nearest_edge_including_top(x, y, w, h, expected):
    edge, position = snap(AREA, x, y, w, h)
    assert edge == expected[0]
    assert position == pytest.approx(expected[1], abs=0.02)


def test_snap_clamps_position():
    assert snap(AREA, 1880, -10, BAR, L) == ("right", 0.0)
    assert snap(AREA, 1880, -500, BAR, L)[0] == "top"
    assert snap(AREA, 1880, 5000, BAR, L) == ("right", 1.0)


@pytest.mark.parametrize("area", [AREA, (-1920, 0, 1920, 1080), (1920, 40, 2560, 1400)])
@pytest.mark.parametrize("edge", ["left", "right", "top"])
@pytest.mark.parametrize("position", [0.0, 0.5, 1.0])
def test_bar_and_expanded_stay_inside_area(area, edge, position):
    ax, ay, aw, ah = area
    for x, y, w, h in (bar_rect(area, edge, position, L), expanded_rect(area, edge, position, L, 320, 420)):
        assert ax <= x and x + w <= ax + aw
        assert ay <= y and y + h <= ay + ah
