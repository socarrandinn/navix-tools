from PySide6.QtCore import QRect, Qt
from PySide6.QtWidgets import QLabel

from dock.registry import LoadedTool
from dock.tool import Tool
from dock.tray import TrayPanel, popup_rect

AREA = (0, 0, 1920, 1032)  # barra de tareas abajo: 48 px


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


def make(qtbot):
    loaded = [LoadedTool("contador", CountingTool(), None), LoadedTool("otra", OtherTool(), None),
              LoadedTool("rota", None, "no se pudo importar")]
    panel = TrayPanel(loaded, width=320, height=300)
    qtbot.addWidget(panel)
    return panel, loaded


def test_popup_sits_above_a_bottom_tray_icon_inside_the_screen():
    anchor = QRect(1700, 1040, 24, 24)
    x, y, w, h = popup_rect(AREA, anchor, 320, 300)
    assert (w, h) == (320, 300)
    assert y + h <= 1032 and y + h >= 1032 - 16
    assert x <= 1712 <= x + w
    assert x + w <= 1920


def test_popup_clamps_to_the_right_edge():
    x, _, w, _ = popup_rect(AREA, QRect(1900, 1040, 24, 24), 320, 300)
    assert x + w <= 1920 - 8


def test_popup_goes_under_a_top_taskbar():
    area = (0, 48, 1920, 1032)
    _, y, _, _ = popup_rect(area, QRect(1700, 10, 24, 24), 320, 300)
    assert 48 <= y <= 48 + 16


def test_popup_without_anchor_uses_bottom_right_corner():
    x, y, w, h = popup_rect(AREA, QRect(), 320, 300)
    assert x + w >= 1920 - 16 and y + h >= 1032 - 16


def test_one_tab_per_tool_and_tabs_switch_the_app(qtbot):
    panel, _ = make(qtbot)
    assert list(panel.tabs) == ["contador", "otra", "rota"]
    assert panel.current == "contador"
    qtbot.mouseClick(panel.tabs["otra"], Qt.MouseButton.LeftButton)
    assert panel.current == "otra"
    assert panel.stack.currentWidget() is panel.cards["otra"]
    assert panel.title.text() == "Otra"
    assert panel.tabs["otra"].isChecked() and not panel.tabs["contador"].isChecked()


def test_failed_tool_shows_its_error(qtbot):
    panel, _ = make(qtbot)
    assert panel.cards["rota"].error_label.text() == "no se pudo importar"


def test_tools_refresh_only_while_the_popup_is_open(qtbot):
    panel, loaded = make(qtbot)
    tool = loaded[0].tool
    assert tool.refreshes == 0
    panel.open_at(AREA, QRect(1700, 1040, 24, 24))
    assert panel.isVisible()
    assert tool.refreshes == 1
    assert all(timer.isActive() for timer in panel.timers)
    panel.hide()
    assert not any(timer.isActive() for timer in panel.timers)


def test_toggle_closes_an_open_popup(qtbot):
    panel, _ = make(qtbot)
    panel.toggle(AREA, QRect(1700, 1040, 24, 24))
    assert panel.isVisible()
    panel.toggle(AREA, QRect(1700, 1040, 24, 24))
    assert not panel.isVisible()
