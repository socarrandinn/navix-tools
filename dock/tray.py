"""Panel de la bandeja del sistema: las mismas apps en una ventana flotante sobre el ícono de Navix.

Es independiente de la barra del borde (que se puede ocultar): sus herramientas se refrescan
solo mientras la ventana está abierta, y se cierra al hacer clic afuera.
"""

from __future__ import annotations

from PySide6.QtCore import QRect, QRectF, QSize, Qt, QTimer
from PySide6.QtGui import QPainter, QPainterPath
from PySide6.QtWidgets import QHBoxLayout, QLabel, QStackedWidget, QToolButton, QVBoxLayout, QWidget

from .geometry import ICON, MARGIN, PANEL_HEIGHT, Rect
from .icons import svg_icon
from .liquid import paint_liquid
from .panel import APP_ICON, STYLE, Card
from .registry import LoadedTool
from .theme import R_SURFACE, themed
from .tool import Tool

TRAY_STYLE = STYLE + themed("""
QToolButton#trayTab { background: transparent; border: none; border-radius: @controlpx; font-weight: 600; }
QToolButton#trayTab:hover { background: rgba(255, 255, 255, 30); }
QToolButton#trayTab:checked { background: rgba(255, 255, 255, 64); }
""")


def _clamp(value: float, low: float, high: float) -> float:
    return max(low, min(high, value))


def popup_rect(area: Rect, anchor: QRect, width: int, height: int, margin: int = MARGIN) -> Rect:
    """Ventana sobre el ícono de la bandeja (o debajo, si la barra de tareas está arriba)."""
    ax, ay, aw, ah = area
    width, height = min(width, aw - 2 * margin), min(height, ah - 2 * margin)
    center = anchor.center().x() if anchor.isValid() else ax + aw
    x = round(_clamp(center - width / 2, ax + margin, ax + aw - margin - width))
    top_taskbar = anchor.isValid() and anchor.center().y() < ay + ah / 2
    y = ay + margin if top_taskbar else ay + ah - margin - height
    return x, y, width, height


class TrayPanel(QWidget):
    def __init__(self, loaded: list[LoadedTool], width: int = 320, height: int = PANEL_HEIGHT):
        super().__init__(None, Qt.WindowType.Popup | Qt.WindowType.FramelessWindowHint
                         | Qt.WindowType.NoDropShadowWindowHint)
        self.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground)
        self.setStyleSheet(TRAY_STYLE)
        self.popup_width, self.popup_height = width, height
        self.current: str | None = None
        self.cards: dict[str, Card] = {}
        self.tabs: dict[str, QToolButton] = {}
        self._titles: dict[str, str] = {}
        self._tools: list[tuple[Tool, Card]] = []
        self.timers: list[QTimer] = []

        layout = QVBoxLayout(self)
        layout.setContentsMargins(14, 12, 14, 14)
        header = QHBoxLayout()
        self.title = QLabel("")
        self.title.setObjectName("panelTitle")
        header.addWidget(self.title)
        header.addStretch(1)
        self.tab_row = QHBoxLayout()
        self.tab_row.setSpacing(4)
        header.addLayout(self.tab_row)
        layout.addLayout(header)
        self.stack = QStackedWidget()
        layout.addWidget(self.stack)
        for item in loaded:
            self._add_tool(item)
        if self.cards:
            self.show_tool(next(iter(self.cards)))

    def _add_tool(self, item: LoadedTool) -> None:
        tool = item.tool
        if tool is None:
            card, title, icon = Card(None, item.error), item.name, "!"
        else:
            title, icon = tool.title or item.name, tool.icon
            try:
                card = Card(tool.create_widget())
            except Exception as exc:  # noqa: BLE001
                card, icon = Card(None, f"{type(exc).__name__}: {exc}"), "!"
            else:
                self._tools.append((tool, card))
                if tool.refresh_ms > 0:
                    timer = QTimer(self)
                    timer.setInterval(tool.refresh_ms)
                    timer.timeout.connect(lambda t=tool, c=card: self._safe_refresh(t, c))
                    self.timers.append(timer)
        self.cards[item.name] = card
        self._titles[item.name] = title
        self.stack.addWidget(card)
        tab = QToolButton()
        tab.setObjectName("trayTab")
        tab.setCheckable(True)
        tab.setFixedSize(ICON, ICON)
        tab.setToolTip(title)
        svg = svg_icon(icon, size=APP_ICON)
        if svg is not None:
            tab.setIcon(svg)
            tab.setIconSize(QSize(APP_ICON, APP_ICON))
        else:
            tab.setText(icon)
        tab.clicked.connect(lambda _checked=False, name=item.name: self.show_tool(name))
        self.tabs[item.name] = tab
        self.tab_row.addWidget(tab)

    def show_tool(self, name: str) -> None:
        self.current = name
        self.stack.setCurrentWidget(self.cards[name])
        self.title.setText(self._titles[name])
        for key, tab in self.tabs.items():
            tab.setChecked(key == name)

    @staticmethod
    def _safe_refresh(tool: Tool, card: Card) -> None:
        try:
            tool.refresh()
        except Exception as exc:  # noqa: BLE001
            card.show_error(f"Error al refrescar: {exc}")

    def open_at(self, area: Rect, anchor: QRect) -> None:
        self.setGeometry(QRect(*popup_rect(area, anchor, self.popup_width, self.popup_height)))
        self.show()
        self.raise_()
        self.activateWindow()

    def toggle(self, area: Rect, anchor: QRect) -> None:
        if self.isVisible():
            self.hide()
        else:
            self.open_at(area, anchor)

    def showEvent(self, event) -> None:
        super().showEvent(event)
        for tool, card in self._tools:
            self._safe_refresh(tool, card)
        for timer in self.timers:
            timer.start()

    def hideEvent(self, event) -> None:
        for timer in self.timers:
            timer.stop()
        super().hideEvent(event)

    def paintEvent(self, event) -> None:
        path = QPainterPath()
        path.addRoundedRect(QRectF(self.rect()).adjusted(0.5, 0.5, -0.5, -0.5), R_SURFACE, R_SURFACE)
        paint_liquid(QPainter(self), path)
