import uuid

from PySide6.QtCore import QEvent, QPointF
from PySide6.QtGui import QEnterEvent
from PySide6.QtWidgets import QLabel

from dock.backdrop import apply_backdrop
from dock.config import DockConfig
from dock.panel import Panel
from dock.registry import LoadedTool
from dock.single import acquire_single_instance
from dock.tool import Tool

AREA = (0, 0, 1920, 1040)


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


def make_panel(qtbot, loaded, area=AREA, **kwargs):
    state = {"area": area}
    panel = Panel(DockConfig(backdrop="none"), loaded, lambda: state["area"], animation_ms=0, **kwargs)
    qtbot.addWidget(panel)
    return panel, state


def rect(panel):
    g = panel.geometry()
    return g.x(), g.y(), g.width(), g.height()


def test_starts_concealed_as_handle_strip(qtbot):
    panel, _ = make_panel(qtbot, [])
    assert panel.revealed is False
    assert rect(panel) == (1914, 12, 6, 1016)


def test_reveal_and_conceal(qtbot):
    panel, _ = make_panel(qtbot, [])
    panel.reveal()
    assert rect(panel) == (1588, 12, 320, 1016)
    panel.conceal()
    assert rect(panel) == (1914, 12, 6, 1016)


def test_leave_conceals_after_delay(qtbot):
    panel, _ = make_panel(qtbot, [], hide_delay_ms=10)
    panel.reveal()
    panel.leaveEvent(QEvent(QEvent.Type.Leave))
    qtbot.waitUntil(lambda: panel.revealed is False, timeout=1000)


def test_enter_cancels_pending_hide(qtbot):
    panel, _ = make_panel(qtbot, [], hide_delay_ms=50)
    panel.reveal()
    panel.leaveEvent(QEvent(QEvent.Type.Leave))
    panel.enterEvent(QEnterEvent(QPointF(), QPointF(), QPointF()))
    qtbot.wait(120)
    assert panel.revealed is True


def test_reposition_follows_area_change(qtbot):
    panel, state = make_panel(qtbot, [])
    panel.reveal()
    state["area"] = (0, 0, 1280, 720)
    panel.reposition()
    assert rect(panel) == (948, 12, 320, 696)


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
