import pytest
import uuid

from PySide6.QtCore import QEvent, QPoint, QPointF
from PySide6.QtGui import QEnterEvent
from PySide6.QtWidgets import QLabel

from dock.config import DockConfig
from dock.geometry import BAR, GAP, bar_length, bar_rect, expanded_rect
from dock.panel import Panel
from dock.registry import LoadedTool
from dock.single import acquire_single_instance
from dock.tool import Tool

AREA = (0, 0, 1920, 1040)
BAR2 = bar_length(2)


class CountingTool(Tool):
    title = "Contador"
    icon = "C"
    refresh_ms = 1000

    def __init__(self):
        self.refreshes = 0

    def create_widget(self):
        return QLabel("ok")

    def refresh(self):
        self.refreshes += 1


class OtherTool(CountingTool):
    title = "Otra"
    icon = "O"


class FailingRefreshTool(CountingTool):
    title = "Falla"

    def refresh(self):
        raise RuntimeError("sin red")


class FailingWidgetTool(CountingTool):
    def create_widget(self):
        raise ValueError("widget roto")


def make_panel(qtbot, loaded=None, config=None, area=AREA, **kwargs):
    state = {"area": area, "saved": [], "closed": 0}

    def on_close():
        state["closed"] += 1

    if loaded is None:
        loaded = [LoadedTool("contador", CountingTool(), None), LoadedTool("otra", OtherTool(), None)]
    kwargs.setdefault("fit_content", False)
    panel = Panel(config or DockConfig(), loaded, lambda: state["area"], animation_ms=0,
                  panel_height=400, on_config_change=state["saved"].append, on_close=on_close, **kwargs)
    qtbot.addWidget(panel)
    return panel, state


def rect(panel):
    g = panel.geometry()
    return g.x(), g.y(), g.width(), g.height()


def enter(panel):
    panel.enterEvent(QEnterEvent(QPointF(), QPointF(), QPointF()))


def leave(panel):
    panel.leaveEvent(QEvent(QEvent.Type.Leave))


def test_starts_collapsed_as_small_bar_with_one_icon_per_app(qtbot):
    panel, _ = make_panel(qtbot)
    assert rect(panel) == bar_rect(AREA, "right", 0.5, BAR2)
    assert rect(panel)[0] + BAR == 1920
    assert panel.revealed is False
    assert panel.flyout.isHidden()
    assert [b.text() for b in panel.tool_buttons.values()] == ["C", "O"]
    assert panel.tool_buttons["contador"].toolTip() == "Contador"


def test_click_icon_opens_that_app_next_to_bar(qtbot):
    panel, _ = make_panel(qtbot)
    panel.tool_buttons["otra"].click()
    assert panel.revealed is True
    assert panel.current == "otra"
    assert panel.stack.currentWidget() is panel.cards["otra"]
    assert panel.title.text() == "Otra"
    assert rect(panel) == expanded_rect(AREA, "right", 0.5, BAR2, 320, 400)
    assert panel.tool_buttons["otra"].isChecked()
    assert not panel.tool_buttons["contador"].isChecked()


def test_click_same_icon_collapses(qtbot):
    panel, _ = make_panel(qtbot)
    panel.tool_buttons["otra"].click()
    panel.tool_buttons["otra"].click()
    assert panel.revealed is False
    assert rect(panel)[2] == BAR
    assert not panel.tool_buttons["otra"].isChecked()


def test_click_other_icon_switches_app_without_collapsing(qtbot):
    panel, _ = make_panel(qtbot)
    panel.tool_buttons["contador"].click()
    panel.tool_buttons["otra"].click()
    assert panel.revealed is True
    assert panel.current == "otra"


def test_bar_stays_on_screen_edge_side(qtbot):
    right, _ = make_panel(qtbot)
    right.open_tool("contador")
    right.layout().activate()
    assert right.bar_column.geometry().x() > right.flyout.geometry().x()
    left, _ = make_panel(qtbot, config=DockConfig(edge="left"))
    left.open_tool("contador")
    left.layout().activate()
    assert left.bar_column.geometry().x() < left.flyout.geometry().x()


def test_leave_collapses_after_delay(qtbot):
    panel, _ = make_panel(qtbot, hide_delay_ms=10)
    panel.open_tool("contador")
    leave(panel)
    qtbot.waitUntil(lambda: panel.revealed is False, timeout=1000)


def test_enter_cancels_pending_collapse(qtbot):
    panel, _ = make_panel(qtbot, hide_delay_ms=50)
    panel.open_tool("contador")
    leave(panel)
    enter(panel)
    qtbot.wait(120)
    assert panel.revealed is True


def test_hover_alone_does_not_expand(qtbot):
    panel, _ = make_panel(qtbot)
    enter(panel)
    qtbot.wait(50)
    assert panel.revealed is False


def test_pinned_config_starts_with_first_app_open_and_ignores_leave(qtbot):
    panel, _ = make_panel(qtbot, config=DockConfig(pinned=True), hide_delay_ms=10)
    assert panel.revealed is True
    assert panel.current == "contador"
    leave(panel)
    qtbot.wait(60)
    assert panel.revealed is True


def test_toggle_pin_saves_config(qtbot):
    panel, state = make_panel(qtbot)
    panel.open_tool("contador")
    panel.toggle_pin()
    assert state["saved"][-1].pinned is True
    assert panel.pin_button.isChecked()
    panel.toggle_pin()
    assert state["saved"][-1].pinned is False


def test_drag_bar_to_left_snaps_and_saves(qtbot):
    panel, state = make_panel(qtbot)
    start = QPoint(1890, 500)
    panel.begin_drag(start)
    panel.drag_to(QPoint(100, 400))
    assert panel.dragging is True
    panel.end_drag(QPoint(100, 400))
    saved = state["saved"][-1]
    assert saved.edge == "left"
    assert 0.0 < saved.position < 0.5
    x, y, w, h = rect(panel)
    assert (x, w) == (0, BAR)
    assert panel.revealed is False


def test_small_move_is_not_a_drag(qtbot):
    panel, state = make_panel(qtbot)
    enter(panel)
    before = rect(panel)
    panel.begin_drag(QPoint(1890, 500))
    panel.drag_to(QPoint(1892, 501))
    panel.end_drag(QPoint(1892, 501))
    assert state["saved"] == []
    assert rect(panel) == before


def test_app_opens_inward_after_moving_to_left(qtbot):
    panel, _ = make_panel(qtbot)
    panel.begin_drag(QPoint(1890, 500))
    panel.drag_to(QPoint(100, 500))
    panel.end_drag(QPoint(100, 500))
    panel.open_tool("contador")
    assert rect(panel)[0] == 0
    panel.layout().activate()
    assert panel.bar_column.geometry().x() < panel.flyout.geometry().x()


def test_app_close_button_only_closes_the_panel(qtbot):
    panel, state = make_panel(qtbot, config=DockConfig(pinned=True))
    assert panel.revealed
    panel.close_button.click()
    assert panel.revealed is False
    assert state["closed"] == 0


def test_settings_icon_opens_a_menu_with_settings_pin_and_quit(qtbot):
    panel, state = make_panel(qtbot)
    shown = []
    panel.exec_menu = lambda menu, pos: shown.append([a.text() for a in menu.actions() if a.text()])
    panel.settings_button.click()
    assert shown == [["Configuración", "Fijar panel", "Salir"]]
    assert not hasattr(panel, "quit_button")


def test_reposition_follows_area_change(qtbot):
    panel, state = make_panel(qtbot)
    panel.open_tool("contador")
    state["area"] = (0, 0, 1280, 720)
    panel.reposition()
    x, y, w, h = rect(panel)
    assert (x, w) == (1280 - BAR - GAP - 320, BAR + GAP + 320)
    assert y + h <= 720 - 12


def test_expanded_height_fits_small_content(qtbot):
    panel, _ = make_panel(qtbot, fit_content=True)
    panel.open_tool("contador")
    h = rect(panel)[3]
    assert BAR2 <= h < 400


def test_initial_refresh_and_timers(qtbot):
    tool = CountingTool()
    panel, _ = make_panel(qtbot, [LoadedTool("contador", tool, None)])
    assert list(panel.cards) == ["contador"]
    assert tool.refreshes == 1
    assert panel.timers[0].interval() == 1000


def test_failing_tools_get_error_cards_and_others_work(qtbot):
    good = CountingTool()
    panel, _ = make_panel(qtbot, [
        LoadedTool("roto", None, "ModuleNotFoundError: x"),
        LoadedTool("falla", FailingRefreshTool(), None),
        LoadedTool("widget", FailingWidgetTool(), None),
        LoadedTool("bueno", good, None),
    ])
    assert "ModuleNotFoundError" in panel.cards["roto"].error_label.text()
    assert "sin red" in panel.cards["falla"].error_label.text()
    assert "widget roto" in panel.cards["widget"].error_label.text()
    assert panel.cards["bueno"].error_label.text() == ""
    assert panel.tool_buttons["roto"].text() == "!"
    assert good.refreshes == 1


def test_no_tools_still_shows_bar(qtbot):
    panel, _ = make_panel(qtbot, [])
    assert rect(panel)[2] == BAR
    assert panel.tool_buttons == {}


def test_single_instance(qapp):
    name = f"ipdock-test-{uuid.uuid4().hex}"
    first = acquire_single_instance(name)
    assert first is not None
    assert acquire_single_instance(name) is None
    first.close()
    third = acquire_single_instance(name)
    assert third is not None
    third.close()


def test_grip_is_a_drawn_handle_with_move_cursor(qtbot):
    from PySide6.QtCore import Qt

    from dock.panel import Grip

    panel, _ = make_panel(qtbot)
    assert isinstance(panel.grip, Grip)
    assert panel.grip.cursor().shape() == Qt.CursorShape.SizeAllCursor
    assert panel.grip.toolTip().startswith("Arrastrá")


@pytest.mark.parametrize("edge", ["right", "left", "top"])
def test_grip_hugs_its_dots_first_in_the_column(qtbot, edge):
    from dock.geometry import GRIP

    panel, _ = make_panel(qtbot, config=DockConfig(edge=edge))
    panel.show()
    qtbot.waitExposed(panel)
    qtbot.wait(20)
    # sin relleno: el agarre mide lo que miden sus puntos, más largo a lo largo de la barra
    along, across = (panel.grip.width(), panel.grip.height()) if edge == "top" else (panel.grip.height(), panel.grip.width())
    assert along == GRIP
    assert across < GRIP
    layout = panel.icons_box.layout()
    assert layout.itemAt(0).widget() is panel.grip
    grip = panel.grip.geometry()
    first = panel.tool_buttons["contador"].geometry()
    if edge == "top":
        assert grip.right() < first.left()
    else:
        assert grip.bottom() < first.top()


def test_grip_has_no_hover_background(qtbot):
    from PySide6.QtGui import QImage

    panel, _ = make_panel(qtbot)
    panel.show()
    qtbot.waitExposed(panel)

    def render():
        image = QImage(panel.grip.size(), QImage.Format.Format_ARGB32)
        image.fill(0)
        panel.grip.render(image)
        return image

    idle = render()
    panel.grip.underMouse = lambda: True
    assert render() == idle


def test_drag_from_grip_reaches_panel(qtbot):
    from PySide6.QtCore import Qt

    panel, state = make_panel(qtbot)
    panel.show()
    qtbot.waitExposed(panel)
    start = panel.grip.mapToGlobal(panel.grip.rect().center())
    qtbot.mousePress(panel.grip, Qt.MouseButton.LeftButton, pos=panel.grip.rect().center())
    assert panel._press_global is not None
    panel.end_drag(start)


def test_drag_to_top_makes_horizontal_bar_that_opens_down(qtbot):
    panel, state = make_panel(qtbot)
    panel.begin_drag(QPoint(1890, 500))
    panel.drag_to(QPoint(960, 20))
    panel.end_drag(QPoint(960, 20))
    assert state["saved"][-1].edge == "top"
    x, y, w, h = rect(panel)
    assert (y, w, h) == (0, BAR2, BAR)
    panel.open_tool("contador")
    assert rect(panel)[1] == 0
    panel.layout().activate()
    assert panel.bar_column.geometry().y() < panel.flyout.geometry().y()
    assert panel.bar_column.geometry().height() == BAR


def test_top_config_starts_horizontal(qtbot):
    panel, _ = make_panel(qtbot, config=DockConfig(edge="top"))
    assert rect(panel) == bar_rect(AREA, "top", 0.5, BAR2)


def test_no_window_mask_so_edges_stay_antialiased(qtbot):
    panel, _ = make_panel(qtbot)
    assert panel.mask().isEmpty()
    panel.open_tool("contador")
    assert panel.mask().isEmpty()


def test_opening_starts_a_decaying_wobble(qtbot):
    panel, _ = make_panel(qtbot)
    panel.animation_ms = 60
    panel.wobble_ms = 120
    panel.show()
    qtbot.waitExposed(panel)
    panel.open_tool("contador")
    qtbot.waitUntil(lambda: panel.wobble > 0.5, timeout=1000)
    qtbot.waitUntil(lambda: panel.wobble == 0.0, timeout=2000)


def test_hover_makes_the_droplet_jiggle(qtbot):
    panel, _ = make_panel(qtbot)
    panel.wobble_ms = 120
    panel.show()
    qtbot.waitExposed(panel)
    enter(panel)
    qtbot.waitUntil(lambda: panel.wobble > 0.2, timeout=1000)


def test_svg_icon_names_render_as_icons(qtbot):
    class SvgTool(CountingTool):
        icon = "network"

    panel, _ = make_panel(qtbot, [LoadedTool("red", SvgTool(), None)])
    button = panel.tool_buttons["red"]
    assert button.text() == ""
    assert not button.icon().isNull()
    assert not panel.pin_button.icon().isNull()
    assert not panel.close_button.icon().isNull()


def test_settings_menu_entry_opens_settings(qtbot):
    opened = []
    panel, _ = make_panel(qtbot, on_settings=lambda: opened.append(1))
    menu = panel.build_menu()
    next(a for a in menu.actions() if a.text() == "Configuración").trigger()
    assert opened == [1]
    assert not panel.settings_button.icon().isNull()

def test_apply_config_moves_and_resizes_live(qtbot):
    from dataclasses import replace

    panel, _ = make_panel(qtbot)
    panel.apply_config(replace(panel.config, edge="top", width=360))
    assert rect(panel) == bar_rect(AREA, "top", 0.5, panel.bar_len)
    panel.open_tool("contador")
    assert rect(panel)[2] == 360


def test_liquid_off_disables_wobble(qtbot):
    panel, _ = make_panel(qtbot, config=DockConfig(liquid=False))
    panel.show()
    qtbot.waitExposed(panel)
    panel.open_tool("contador")
    qtbot.wait(50)
    assert panel.wobble == 0.0


def test_turning_liquid_off_stops_the_wave(qtbot):
    from dataclasses import replace

    panel, _ = make_panel(qtbot)
    panel.animation_ms = 60
    panel.wobble_ms = 2000
    panel.show()
    qtbot.waitExposed(panel)
    panel.open_tool("contador")
    qtbot.waitUntil(lambda: panel.wobble > 0.5, timeout=1000)
    panel.apply_config(replace(panel.config, liquid=False))
    assert panel.wobble == 0.0
    qtbot.wait(50)
    assert panel.wobble == 0.0


@pytest.mark.parametrize("edge", ["right", "left", "top"])
def test_content_has_breathing_room_from_droplet_edges(qtbot, edge):
    from dock.geometry import ICON

    panel, _ = make_panel(qtbot, config=DockConfig(edge=edge))
    flyout = panel.flyout.layout().contentsMargins()
    assert min(flyout.left(), flyout.right()) >= 14
    assert min(flyout.top(), flyout.bottom()) >= 12
    assert (BAR - ICON) // 2 >= 7
    card = panel.cards["contador"].layout().contentsMargins()
    assert min(card.left(), card.top(), card.right(), card.bottom()) >= 14


def gap_point(panel):
    """Punto en el hueco entre la barra y la app, a la altura del centro de la barra."""
    bar = panel.bar_shape_rect()
    flyout = panel.flyout.geometry()
    return QPoint(round((bar.left() + flyout.right()) / 2), round(bar.center().y()))


def test_open_app_stays_joined_to_the_bar_by_a_thin_neck(qtbot):
    from dock.liquid import NECK_MAX

    panel, _ = make_panel(qtbot)
    panel.open_tool("contador")
    assert panel.bud == 1.0
    flyout = panel.flyout.geometry()
    assert panel.shape().contains(QPointF(flyout.center()))
    assert panel.shape().contains(QPointF(gap_point(panel)))
    assert 0 < panel._neck_thickness() < NECK_MAX
    gap = gap_point(panel)
    joined = [y for y in range(rect(panel)[3]) if panel.shape().contains(QPointF(gap.x(), y + 0.5))]
    assert len(joined) <= NECK_MAX
    assert panel.flyout_opacity() == 1.0


def test_half_open_drop_is_still_joined_by_a_neck(qtbot):
    panel, _ = make_panel(qtbot)
    panel.open_tool("contador")
    panel.set_bud(0.4)
    assert panel.shape().contains(QPointF(gap_point(panel)))
    assert panel.flyout_opacity() == 0.0


def test_bar_keeps_its_size_and_place_when_open(qtbot):
    panel, _ = make_panel(qtbot)
    collapsed = bar_rect(AREA, "right", 0.5, BAR2)
    panel.open_tool("contador")
    bar = panel.bar_shape_rect()
    assert (round(bar.width()), round(bar.height())) == (BAR, BAR2)
    assert round(bar.top()) + rect(panel)[1] == collapsed[1]


def test_bud_animates_open_and_closed(qtbot):
    panel, _ = make_panel(qtbot)
    panel.animation_ms = 60
    panel.show()
    qtbot.waitExposed(panel)
    panel.open_tool("contador")
    assert panel.bud < 1.0
    qtbot.waitUntil(lambda: panel.bud == 1.0, timeout=2000)
    panel.conceal()
    qtbot.waitUntil(lambda: rect(panel)[2] == BAR, timeout=2000)
    assert panel.bud == 0.0


def bar_center(panel):
    x, y, w, h = rect(panel)
    return QPoint(x + w // 2, y + h // 2)


def test_small_pull_stretches_but_stays_stuck(qtbot):
    panel, state = make_panel(qtbot)
    start = bar_center(panel)
    panel.begin_drag(start)
    panel.drag_to(start - QPoint(40, 0))
    assert panel.dragging and not panel.detached
    x, y, w, h = rect(panel)
    assert w > BAR and x + w == 1920
    assert panel.shape().contains(QPointF(w - 1, h / 2))
    panel.end_drag(start - QPoint(40, 0))
    assert rect(panel) == bar_rect(AREA, "right", 0.5, BAR2)
    assert panel.config.edge == "right"


def test_pull_past_threshold_detaches_into_a_free_drop(qtbot):
    panel, _ = make_panel(qtbot)
    start = bar_center(panel)
    panel.begin_drag(start)
    panel.drag_to(start - QPoint(150, 0))
    assert panel.detached
    x, y, w, h = rect(panel)
    assert (w, h) == (BAR, BAR2)
    assert x + w < 1920
    assert not panel.shape().contains(QPointF(0.5, 0.5))


def test_sliding_along_the_edge_does_not_detach(qtbot):
    panel, state = make_panel(qtbot)
    start = bar_center(panel)
    panel.begin_drag(start)
    panel.drag_to(start + QPoint(0, 200))
    assert not panel.detached
    panel.end_drag(start + QPoint(0, 200))
    assert state["saved"][-1].edge == "right"
    assert state["saved"][-1].position > 0.5


def test_neck_between_bar_and_app_never_exceeds_30px(qtbot):
    from dock.liquid import NECK_MAX

    panel, _ = make_panel(qtbot)
    panel.open_tool("contador")
    for bud in (0.05, 0.3, 0.6):
        panel.set_bud(bud)
        assert panel._neck_thickness() <= NECK_MAX
    start = bar_center(panel)
    panel.conceal()
    panel.begin_drag(bar_center(panel))
    panel.drag_to(bar_center(panel) - QPoint(10, 0))
    x, y, w, h = rect(panel)
    shape = panel.shape()
    inside = [yy for yy in range(h) if shape.contains(QPointF(w - 3, yy + 0.5))]
    assert len(inside) <= NECK_MAX + 2



@pytest.mark.parametrize("edge, pull", [("right", QPoint(-30, 0)), ("left", QPoint(30, 0)), ("top", QPoint(0, 30))])
def test_stretching_keeps_icons_centered_inside_the_drop(qtbot, edge, pull):
    panel, _ = make_panel(qtbot, config=DockConfig(edge=edge))
    panel.show()
    qtbot.waitExposed(panel)
    start = bar_center(panel)
    panel.begin_drag(start)
    panel.drag_to(start + pull)
    assert panel._pull > 0 and not panel.detached
    qtbot.wait(20)
    x, y, w, h = rect(panel)
    button = panel.tool_buttons["contador"]
    center = button.mapTo(panel, button.rect().center())
    if edge == "right":
        body = (0, BAR)
        value = center.x()
    elif edge == "left":
        body = (w - BAR, w)
        value = center.x()
    else:
        body = (h - BAR, h)
        value = center.y()
    assert body[0] + 15 <= value <= body[1] - 15


@pytest.mark.parametrize("edge", ["right", "top"])
def test_icons_have_room_at_the_bar_ends_and_sides(qtbot, edge):
    panel, _ = make_panel(qtbot, config=DockConfig(edge=edge))
    panel.show()
    qtbot.waitExposed(panel)
    qtbot.wait(20)
    bar = panel.bar_shape_rect()

    def at(widget):
        return widget.geometry().translated(widget.parentWidget().mapTo(panel, QPoint(0, 0)))

    first, gear = at(panel.grip), at(panel.settings_button)
    if edge == "right":
        assert first.top() - bar.top() >= 16
        assert bar.bottom() - gear.bottom() >= 16
        assert first.left() - bar.left() >= 8
    else:
        assert first.left() - bar.left() >= 16
        assert bar.right() - gear.right() >= 16
        assert bar.bottom() - first.bottom() >= 8


def test_opening_an_app_cancels_a_drag_in_progress(qtbot):
    panel, _ = make_panel(qtbot)
    start = bar_center(panel)
    panel.begin_drag(start)
    panel.drag_to(start - QPoint(30, 0))
    panel.open_tool("contador")
    assert panel._press_global is None and not panel.dragging and panel._pull == 0.0
    assert panel.layout().contentsMargins().right() == 0
    panel.drag_to(start - QPoint(40, 0))
    assert rect(panel) == expanded_rect(AREA, "right", 0.5, BAR2, 320, 400)


def test_icon_buttons_are_round_ghost_buttons(qtbot):
    import re

    from dock.panel import HEADER_BUTTON, ICON, STYLE

    panel, _ = make_panel(qtbot)
    for button in (panel.pin_button, panel.close_button):
        assert button.width() == button.height() == HEADER_BUTTON
        assert button.text() == ""
    for selector, size in (("QPushButton#headerButton", HEADER_BUTTON), ("QToolButton#appIcon", ICON)):
        block = re.search(re.escape(selector) + r" \{([^}]*)\}", STYLE).group(1)
        assert f"border-radius: {size // 2}px" in block
        assert "border: none" in block and "background: transparent" in block
        checked = re.search(re.escape(selector) + r":checked \{([^}]*)\}", STYLE).group(1)
        assert "border" not in checked


def test_menu_has_icons_and_hover_style(qtbot):
    panel, _ = make_panel(qtbot)
    menu = panel.build_menu()
    actions = [a for a in menu.actions() if a.text()]
    assert all(not a.icon().isNull() for a in actions)
    style = menu.styleSheet()
    assert "QMenu::item:selected" in style
    assert "border-radius" in style




def _svg_panel(qtbot, edge="right"):
    class SvgTool(CountingTool):
        icon = "network"

    panel, state = make_panel(qtbot, [LoadedTool("red", SvgTool(), None)], config=DockConfig(edge=edge))
    panel.show()
    qtbot.waitExposed(panel)
    return panel, state


@pytest.mark.parametrize("edge", ["right", "left", "top"])
def test_hovered_icon_swells_the_bar_past_its_thickness(qtbot, edge):
    from dock.panel import APP_ICON, SWELL

    panel, state = _svg_panel(qtbot, edge)
    button = panel.tool_buttons["red"]
    collapsed = rect(panel)
    button.enterEvent(QEnterEvent(QPointF(), QPointF(), QPointF()))
    assert panel.swell == 1.0
    x, y, w, h = rect(panel)
    # la ventana gana espacio hacia adentro; la barra sigue pegada al borde
    expected = {"right": (collapsed[0] - SWELL, y, collapsed[2] + SWELL, h),
                "left": (collapsed[0], y, collapsed[2] + SWELL, h),
                "top": (x, collapsed[1], w, collapsed[3] + SWELL)}[edge]
    assert (x, y, w, h) == expected
    bar = panel.bar_shape_rect()
    center = button.mapTo(panel, button.rect().center())
    beyond = {"right": QPointF(bar.left() - SWELL / 2, center.y()),
              "left": QPointF(bar.right() + SWELL / 2, center.y()),
              "top": QPointF(center.x(), bar.bottom() + SWELL / 2)}[edge]
    assert panel.shape().contains(beyond)
    # sin efecto de escala: el ícono queda de su tamaño
    assert button.iconSize().width() == APP_ICON


def test_swell_retracts_and_window_shrinks_when_mouse_leaves(qtbot):
    panel, _ = _svg_panel(qtbot)
    button = panel.tool_buttons["red"]
    collapsed = rect(panel)
    button.enterEvent(QEnterEvent(QPointF(), QPointF(), QPointF()))
    panel.leaveEvent(QEvent(QEvent.Type.Leave))
    assert panel.swell == 0.0
    assert rect(panel) == collapsed


def test_clicking_the_bulge_opens_the_hovered_app(qtbot):
    from PySide6.QtCore import Qt

    panel, _ = _svg_panel(qtbot)
    button = panel.tool_buttons["red"]
    button.enterEvent(QEnterEvent(QPointF(), QPointF(), QPointF()))
    bar = panel.bar_shape_rect()
    center = button.mapTo(panel, button.rect().center())
    spot = QPoint(round(bar.left() - 4), center.y())
    qtbot.mouseClick(panel, Qt.MouseButton.LeftButton, pos=spot)
    assert panel.revealed and panel.current == "red"


def test_dragging_cancels_the_swell(qtbot):
    panel, _ = _svg_panel(qtbot)
    panel.tool_buttons["red"].enterEvent(QEnterEvent(QPointF(), QPointF(), QPointF()))
    start = bar_center(panel)
    panel.begin_drag(start)
    panel.drag_to(start + QPoint(0, 30))
    assert panel.swell == 0.0
    panel.end_drag(start + QPoint(0, 30))
