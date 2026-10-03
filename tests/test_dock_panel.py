import uuid

from PySide6.QtCore import QEvent, QPoint, QPointF
from PySide6.QtGui import QEnterEvent
from PySide6.QtWidgets import QLabel

from dock.config import DockConfig
from dock.geometry import BAR, bar_length, bar_rect, expanded_rect
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
    assert right.bar.geometry().x() > right.flyout.geometry().x()
    left, _ = make_panel(qtbot, config=DockConfig(edge="left"))
    left.open_tool("contador")
    left.layout().activate()
    assert left.bar.geometry().x() < left.flyout.geometry().x()


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
    assert panel.bar.geometry().x() < panel.flyout.geometry().x()


def test_close_button_calls_on_close(qtbot):
    panel, state = make_panel(qtbot)
    panel.open_tool("contador")
    panel.close_button.click()
    assert state["closed"] == 1


def test_context_menu_has_pin_and_close(qtbot):
    panel, _ = make_panel(qtbot)
    texts = [action.text() for action in panel.build_menu().actions() if action.text()]
    assert texts == ["Fijar panel", "Salir"]


def test_reposition_follows_area_change(qtbot):
    panel, state = make_panel(qtbot)
    panel.open_tool("contador")
    state["area"] = (0, 0, 1280, 720)
    panel.reposition()
    x, y, w, h = rect(panel)
    assert (x, w) == (1280 - BAR - 320, BAR + 320)
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
    assert panel.grip.dots() == 6


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
    assert panel.bar.geometry().y() < panel.flyout.geometry().y()
    assert panel.bar.geometry().height() == BAR


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


def test_expand_animation_is_springy(qtbot):
    from PySide6.QtCore import QEasingCurve

    panel, _ = make_panel(qtbot)
    panel.animation_ms = 50
    panel.show()
    qtbot.waitExposed(panel)
    panel.open_tool("contador")
    assert panel.animation.easingCurve().type() == QEasingCurve.Type.OutBack


def test_svg_icon_names_render_as_icons(qtbot):
    class SvgTool(CountingTool):
        icon = "network"

    panel, _ = make_panel(qtbot, [LoadedTool("red", SvgTool(), None)])
    button = panel.tool_buttons["red"]
    assert button.text() == ""
    assert not button.icon().isNull()
    assert not panel.pin_button.icon().isNull()
    assert not panel.close_button.icon().isNull()
