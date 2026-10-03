import uuid

from PySide6.QtCore import QEvent, QPoint, QPointF
from PySide6.QtGui import QEnterEvent
from PySide6.QtWidgets import QLabel

from dock.backdrop import apply_backdrop
from dock.config import DockConfig
from dock.panel import Panel
from dock.registry import LoadedTool
from dock.single import acquire_single_instance
from dock.tool import Tool

AREA = (0, 0, 1920, 1040)
BUBBLE_RIGHT = (1858, 495, 50, 50)
EXPANDED_RIGHT = (1588, 320, 320, 400)


class CountingTool(Tool):
    title = "Contador"
    refresh_ms = 1000

    def __init__(self):
        self.refreshes = 0

    def create_widget(self):
        return QLabel("ok")

    def refresh(self):
        self.refreshes += 1


class FailingRefreshTool(CountingTool):
    title = "Falla"

    def refresh(self):
        raise RuntimeError("sin red")


class FailingWidgetTool(CountingTool):
    def create_widget(self):
        raise ValueError("widget roto")


def make_panel(qtbot, loaded, config=None, area=AREA, **kwargs):
    state = {"area": area, "saved": [], "closed": 0}

    def on_close():
        state["closed"] += 1

    kwargs.setdefault("fit_content", False)
    panel = Panel(config or DockConfig(backdrop="none"), loaded, lambda: state["area"], animation_ms=0,
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


def test_starts_collapsed_as_50px_bubble(qtbot):
    panel, _ = make_panel(qtbot, [])
    assert panel.revealed is False
    assert rect(panel) == BUBBLE_RIGHT
    assert panel.body.isHidden()


def test_reveal_and_conceal(qtbot):
    panel, _ = make_panel(qtbot, [])
    panel.reveal()
    assert rect(panel) == EXPANDED_RIGHT
    assert not panel.body.isHidden()
    panel.conceal()
    assert rect(panel) == BUBBLE_RIGHT


def test_hover_expands_after_short_delay(qtbot):
    panel, _ = make_panel(qtbot, [], hover_delay_ms=10)
    enter(panel)
    assert panel.revealed is False
    qtbot.waitUntil(lambda: panel.revealed, timeout=1000)


def test_press_on_bubble_cancels_hover_expand(qtbot):
    panel, _ = make_panel(qtbot, [], hover_delay_ms=30)
    enter(panel)
    panel.begin_drag(QPoint(1880, 520))
    qtbot.wait(80)
    assert panel.revealed is False


def test_leave_collapses_after_delay(qtbot):
    panel, _ = make_panel(qtbot, [], hide_delay_ms=10)
    panel.reveal()
    leave(panel)
    qtbot.waitUntil(lambda: panel.revealed is False, timeout=1000)


def test_enter_cancels_pending_collapse(qtbot):
    panel, _ = make_panel(qtbot, [], hide_delay_ms=50)
    panel.reveal()
    leave(panel)
    enter(panel)
    qtbot.wait(120)
    assert panel.revealed is True


def test_pinned_config_starts_expanded_and_ignores_leave(qtbot):
    panel, _ = make_panel(qtbot, [], config=DockConfig(backdrop="none", pinned=True), hide_delay_ms=10)
    assert panel.revealed is True
    assert rect(panel) == EXPANDED_RIGHT
    leave(panel)
    qtbot.wait(60)
    assert panel.revealed is True


def test_toggle_pin_saves_config(qtbot):
    panel, state = make_panel(qtbot, [])
    panel.reveal()
    panel.toggle_pin()
    assert state["saved"][-1].pinned is True
    assert panel.pin_button.isChecked()
    panel.toggle_pin()
    assert state["saved"][-1].pinned is False


def test_drag_to_left_snaps_and_saves(qtbot):
    panel, state = make_panel(qtbot, [])
    panel.begin_drag(QPoint(1880, 520))
    panel.drag_to(QPoint(400, 300))
    assert panel.dragging is True
    panel.end_drag(QPoint(400, 300))
    saved = state["saved"][-1]
    assert saved.edge == "left"
    assert 0.0 < saved.position < 0.5
    x, y, w, h = rect(panel)
    assert (x, w, h) == (12, 50, 50)
    assert panel.revealed is False


def test_small_move_is_a_click_that_expands(qtbot):
    panel, state = make_panel(qtbot, [])
    panel.begin_drag(QPoint(1880, 520))
    panel.drag_to(QPoint(1882, 521))
    panel.end_drag(QPoint(1882, 521))
    assert state["saved"] == []
    assert panel.revealed is True


def test_expanded_panel_opens_on_dragged_side(qtbot):
    panel, _ = make_panel(qtbot, [])
    panel.begin_drag(QPoint(1880, 520))
    panel.drag_to(QPoint(100, 520))
    panel.end_drag(QPoint(100, 520))
    panel.reveal()
    assert rect(panel)[0] == 12


def test_close_button_calls_on_close(qtbot):
    panel, state = make_panel(qtbot, [])
    panel.reveal()
    panel.close_button.click()
    assert state["closed"] == 1


def test_context_menu_has_pin_and_close(qtbot):
    panel, _ = make_panel(qtbot, [])
    texts = [action.text() for action in panel.build_menu().actions() if action.text()]
    assert texts == ["Fijar panel", "Salir"]


def test_reposition_follows_area_change(qtbot):
    panel, state = make_panel(qtbot, [])
    panel.reveal()
    state["area"] = (0, 0, 1280, 720)
    panel.reposition()
    assert rect(panel) == (948, 160, 320, 400)


def test_cards_and_initial_refresh(qtbot):
    tool = CountingTool()
    panel, _ = make_panel(qtbot, [LoadedTool("contador", tool, None)])
    assert list(panel.cards) == ["contador"]
    assert tool.refreshes == 1
    assert panel.timers[0].interval() == 1000


def test_failing_tool_shows_error_card_and_others_work(qtbot):
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
    assert good.refreshes == 1


def test_single_instance(qapp):
    name = f"ipdock-test-{uuid.uuid4().hex}"
    first = acquire_single_instance(name)
    assert first is not None
    assert acquire_single_instance(name) is None
    first.close()
    third = acquire_single_instance(name)
    assert third is not None
    third.close()


def test_apply_backdrop_invalid_window_returns_false():
    assert apply_backdrop(0) is False


def test_expanded_height_fits_small_content(qtbot):
    panel, _ = make_panel(qtbot, [LoadedTool("contador", CountingTool(), None)], fit_content=True)
    panel.reveal()
    x, y, w, h = rect(panel)
    assert 80 < h < 400
    assert w == 320
