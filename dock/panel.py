from __future__ import annotations

from dataclasses import replace
from typing import Callable

from PySide6.QtCore import QEasingCurve, QPoint, QPropertyAnimation, QRect, Qt, QTimer
from PySide6.QtGui import QColor, QGuiApplication, QPainter, QPen
from PySide6.QtWidgets import (
    QApplication,
    QFrame,
    QHBoxLayout,
    QLabel,
    QLayout,
    QMenu,
    QPushButton,
    QStackedWidget,
    QToolButton,
    QVBoxLayout,
    QWidget,
)

from .backdrop import apply_backdrop
from .config import DockConfig
from .geometry import BAR, GRIP, ICON, ICON_GAP, PANEL_HEIGHT, Rect, bar_height, bar_rect, expanded_rect, snap
from .registry import LoadedTool
from .tool import Tool

DRAG_THRESHOLD = 4

STYLE = """
QWidget { color: #e6edf3; font-family: 'Segoe UI'; font-size: 13px; background: transparent; }
QLabel#grip { color: #8b949e; font-size: 12px; }
QToolButton#appIcon { border: none; border-radius: 8px; font-size: 13px; font-weight: 600; }
QToolButton#appIcon:hover { background: rgba(255, 255, 255, 40); }
QToolButton#appIcon:checked { background: rgba(88, 166, 255, 110); }
QLabel#panelTitle { font-size: 14px; font-weight: 600; }
QPushButton#headerButton { background: transparent; border: none; border-radius: 6px; padding: 2px 6px;
                           font-size: 13px; }
QPushButton#headerButton:hover { background: rgba(255, 255, 255, 40); }
QPushButton#headerButton:checked { background: rgba(88, 166, 255, 90); }
QFrame#card { background: rgba(255, 255, 255, 14); border: 1px solid rgba(255, 255, 255, 24); border-radius: 10px; }
QLabel#cardError { color: #f85149; }
QPushButton { background: rgba(255, 255, 255, 30); border: 1px solid rgba(255, 255, 255, 40);
              border-radius: 8px; padding: 6px 10px; }
QPushButton:hover { background: rgba(255, 255, 255, 50); }
QPushButton:disabled { color: #6e7681; }
QPushButton[active="true"] { background: rgba(88, 166, 255, 70); border-color: #58a6ff; }
QProgressBar { background: rgba(255, 255, 255, 20); border: none; border-radius: 4px; height: 8px;
               text-align: right; font-size: 11px; }
QProgressBar::chunk { background: #58a6ff; border-radius: 4px; }
"""


class Card(QFrame):
    def __init__(self, body: QWidget | None, error: str | None = None):
        super().__init__()
        self.setObjectName("card")
        layout = QVBoxLayout(self)
        layout.setContentsMargins(12, 10, 12, 10)
        if body is not None:
            layout.addWidget(body)
        self.error_label = QLabel("")
        self.error_label.setObjectName("cardError")
        self.error_label.setWordWrap(True)
        layout.addWidget(self.error_label)
        layout.addStretch(1)
        self.show_error(error or "")

    def show_error(self, text: str) -> None:
        self.error_label.setText(text)
        self.error_label.setVisible(bool(text))


class Panel(QWidget):
    """Barra chica pegada a un borde con un ícono por app; clic en un ícono despliega esa app."""

    def __init__(
        self,
        config: DockConfig,
        loaded: list[LoadedTool],
        screen_area: Callable[[], Rect],
        animation_ms: int = 180,
        hide_delay_ms: int = 700,
        panel_height: int = PANEL_HEIGHT,
        fit_content: bool = True,
        on_config_change: Callable[[DockConfig], None] = lambda config: None,
        on_close: Callable[[], None] | None = None,
    ):
        super().__init__(None, Qt.WindowType.FramelessWindowHint | Qt.WindowType.Tool
                         | Qt.WindowType.WindowStaysOnTopHint)
        self.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground)
        self.setMinimumSize(1, 1)
        self.setStyleSheet(STYLE)
        self.config = config
        self._area = screen_area
        self.animation_ms = animation_ms
        self.panel_height = panel_height
        self.fit_content = fit_content
        self.on_config_change = on_config_change
        self.on_close = on_close or QApplication.quit
        self.revealed = False
        self.backdrop_active = False
        self.dragging = False
        self._press_global: QPoint | None = None
        self._press_offset = QPoint()
        self.current: str | None = None
        self.cards: dict[str, Card] = {}
        self.tool_buttons: dict[str, QToolButton] = {}
        self._titles: dict[str, str] = {}
        self.timers: list[QTimer] = []
        self.bar_h = bar_height(len(loaded))

        self.bar = self._build_bar()
        self.flyout = self._build_flyout()
        for item in loaded:
            self._add_tool(item)
        self.bar.layout().addStretch(1)

        root = QHBoxLayout(self)
        root.setSizeConstraint(QLayout.SizeConstraint.SetNoConstraint)
        root.setContentsMargins(0, 0, 0, 0)
        root.setSpacing(0)
        self._arrange()

        self.hide_timer = QTimer(self)
        self.hide_timer.setSingleShot(True)
        self.hide_timer.setInterval(hide_delay_ms)
        self.hide_timer.timeout.connect(self.conceal)
        self.animation = QPropertyAnimation(self, b"geometry", self)
        self.animation.setEasingCurve(QEasingCurve.Type.OutCubic)
        self.animation.finished.connect(self._after_animation)

        self.flyout.setVisible(False)
        self.setGeometry(QRect(*self._target(False)))
        if config.pinned and self.cards:
            self.reveal()

    # --- construcción -----------------------------------------------------------------------

    def _build_bar(self) -> QWidget:
        bar = QWidget()
        bar.setFixedWidth(BAR)
        layout = QVBoxLayout(bar)
        layout.setContentsMargins((BAR - ICON) // 2, 0, (BAR - ICON) // 2, 4)
        layout.setSpacing(ICON_GAP)
        grip = QLabel("⋯")
        grip.setObjectName("grip")
        grip.setFixedHeight(GRIP)
        grip.setAlignment(Qt.AlignmentFlag.AlignCenter)
        grip.setToolTip("Arrastrá para mover · clic derecho para el menú")
        layout.addWidget(grip)
        return bar

    def _build_flyout(self) -> QWidget:
        flyout = QWidget()
        flyout.setFixedWidth(self.config.width)
        layout = QVBoxLayout(flyout)
        layout.setContentsMargins(12, 8, 8, 12)
        header = QHBoxLayout()
        self.title = QLabel("")
        self.title.setObjectName("panelTitle")
        self.pin_button = QPushButton("📌")
        self.pin_button.setObjectName("headerButton")
        self.pin_button.setCheckable(True)
        self.pin_button.setChecked(self.config.pinned)
        self.pin_button.setToolTip("Fijar panel abierto")
        self.pin_button.clicked.connect(self.toggle_pin)
        self.close_button = QPushButton("✕")
        self.close_button.setObjectName("headerButton")
        self.close_button.setToolTip("Cerrar IPDock")
        self.close_button.clicked.connect(lambda: self.on_close())
        header.addWidget(self.title)
        header.addStretch(1)
        header.addWidget(self.pin_button)
        header.addWidget(self.close_button)
        self.header = header
        layout.addLayout(header)
        self.stack = QStackedWidget()
        layout.addWidget(self.stack)
        return flyout

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
                self._start_refresh(tool, card)
        self.cards[item.name] = card
        self._titles[item.name] = title
        self.stack.addWidget(card)
        button = QToolButton()
        button.setObjectName("appIcon")
        button.setText(icon)
        button.setToolTip(title)
        button.setCheckable(True)
        button.setFixedSize(ICON, ICON)
        button.clicked.connect(lambda _checked=False, name=item.name: self._icon_clicked(name))
        self.tool_buttons[item.name] = button
        self.bar.layout().addWidget(button)

    def _start_refresh(self, tool: Tool, card: Card) -> None:
        self._safe_refresh(tool, card)
        if tool.refresh_ms > 0:
            timer = QTimer(self)
            timer.setInterval(tool.refresh_ms)
            timer.timeout.connect(lambda t=tool, c=card: self._safe_refresh(t, c))
            timer.start()
            self.timers.append(timer)

    @staticmethod
    def _safe_refresh(tool: Tool, card: Card) -> None:
        try:
            tool.refresh()
        except Exception as exc:  # noqa: BLE001
            card.show_error(f"Error al refrescar: {exc}")

    def _arrange(self) -> None:
        """La barra queda del lado del borde de la pantalla y la app se abre hacia adentro."""
        root = self.layout()
        root.removeWidget(self.bar)
        root.removeWidget(self.flyout)
        order = (self.flyout, self.bar) if self.config.edge == "right" else (self.bar, self.flyout)
        for widget in order:
            root.addWidget(widget)

    # --- abrir / cerrar apps ----------------------------------------------------------------

    def _icon_clicked(self, name: str) -> None:
        if self.revealed and self.current == name:
            self.conceal()
            self._sync_buttons()
            return
        self.open_tool(name)

    def open_tool(self, name: str) -> None:
        self.hide_timer.stop()
        self.current = name
        self.stack.setCurrentWidget(self.cards[name])
        self.title.setText(self._titles[name])
        self._move_to(True)
        self._sync_buttons()

    def reveal(self) -> None:
        if self.cards:
            self.open_tool(self.current or next(iter(self.cards)))

    def conceal(self) -> None:
        if self.revealed and not self.config.pinned:
            self._move_to(False)
            self._sync_buttons()

    def _sync_buttons(self) -> None:
        for name, button in self.tool_buttons.items():
            button.setChecked(self.revealed and name == self.current)

    def toggle_pin(self) -> None:
        self._save(pinned=not self.config.pinned)
        self.pin_button.setChecked(self.config.pinned)
        if self.config.pinned and not self.revealed:
            self.reveal()

    def _save(self, **changes) -> None:
        self.config = replace(self.config, **changes)
        self.on_config_change(self.config)

    # --- geometría y animación --------------------------------------------------------------

    def _content_height(self) -> int:
        if not self.fit_content or self.current is None:
            return self.panel_height
        margins = self.flyout.layout().contentsMargins()
        needed = (
            margins.top() + margins.bottom()
            + self.header.sizeHint().height()
            + self.flyout.layout().spacing()
            + self.cards[self.current].sizeHint().height()
        )
        return min(self.panel_height, needed)

    def _target(self, revealed: bool) -> Rect:
        area = self._area()
        if revealed:
            return expanded_rect(area, self.config.edge, self.config.position, self.bar_h,
                                 self.config.width, self._content_height())
        return bar_rect(area, self.config.edge, self.config.position, self.bar_h)

    def _move_to(self, revealed: bool) -> None:
        self.revealed = revealed
        if revealed:
            self.flyout.setVisible(True)
        target = QRect(*self._target(revealed))
        self.animation.stop()
        if self.animation_ms <= 0 or not self.isVisible():
            self.setGeometry(target)
            self._after_animation()
            return
        self.animation.setDuration(self.animation_ms)
        self.animation.setStartValue(self.geometry())
        self.animation.setEndValue(target)
        self.animation.start()

    def _after_animation(self) -> None:
        if not self.revealed:
            self.flyout.setVisible(False)
        self.update()

    def reposition(self, *_args) -> None:
        self.animation.stop()
        self.setGeometry(QRect(*self._target(self.revealed)))

    # --- arrastre de la barra ---------------------------------------------------------------

    def begin_drag(self, global_pos: QPoint) -> None:
        if self.revealed:
            return
        self._press_global = QPoint(global_pos)
        self._press_offset = global_pos - self.pos()
        self.dragging = False

    def drag_to(self, global_pos: QPoint) -> None:
        if self._press_global is None:
            return
        if not self.dragging and (global_pos - self._press_global).manhattanLength() > DRAG_THRESHOLD:
            self.dragging = True
            self.animation.stop()
        if self.dragging:
            self.move(global_pos - self._press_offset)

    def end_drag(self, global_pos: QPoint) -> None:
        if self._press_global is None:
            return
        self.drag_to(global_pos)
        was_dragging = self.dragging
        self._press_global = None
        self.dragging = False
        if not was_dragging:
            return
        edge, position = snap(self._area(), self.x(), self.y(), self.bar_h)
        self._save(edge=edge, position=position)
        self._arrange()
        self._move_to(False)

    # --- eventos ----------------------------------------------------------------------------

    def build_menu(self) -> QMenu:
        menu = QMenu(self)
        pin = menu.addAction("Soltar panel" if self.config.pinned else "Fijar panel")
        pin.triggered.connect(self.toggle_pin)
        menu.addSeparator()
        close = menu.addAction("Salir")
        close.triggered.connect(lambda: self.on_close())
        return menu

    def contextMenuEvent(self, event) -> None:
        self.hide_timer.stop()
        self.build_menu().exec(event.globalPos())

    def mousePressEvent(self, event) -> None:
        if event.button() == Qt.MouseButton.LeftButton:
            self.begin_drag(event.globalPosition().toPoint())
        super().mousePressEvent(event)

    def mouseMoveEvent(self, event) -> None:
        self.drag_to(event.globalPosition().toPoint())
        super().mouseMoveEvent(event)

    def mouseReleaseEvent(self, event) -> None:
        if event.button() == Qt.MouseButton.LeftButton:
            self.end_drag(event.globalPosition().toPoint())
        super().mouseReleaseEvent(event)

    def enterEvent(self, event) -> None:
        self.hide_timer.stop()
        super().enterEvent(event)

    def leaveEvent(self, event) -> None:
        if self.revealed and not self.config.pinned:
            self.hide_timer.start()
        super().leaveEvent(event)

    def showEvent(self, event) -> None:
        super().showEvent(event)
        if self.config.backdrop == "acrylic" and not self.backdrop_active:
            self.backdrop_active = apply_backdrop(int(self.winId()))

    def paintEvent(self, event) -> None:
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)
        painter.setPen(Qt.PenStyle.NoPen)
        alpha = 120 if self.backdrop_active else 235
        painter.setBrush(QColor(22, 24, 30, alpha))
        painter.drawRoundedRect(self.rect().adjusted(0, 0, -1, -1), 10, 10)
        if self.revealed:
            x = self.bar.geometry().left() if self.config.edge == "right" else self.bar.geometry().right()
            painter.setPen(QPen(QColor(255, 255, 255, 30), 1))
            painter.drawLine(x, 8, x, self.height() - 8)


def primary_area() -> Rect:
    geometry = QGuiApplication.primaryScreen().availableGeometry()
    return geometry.x(), geometry.y(), geometry.width(), geometry.height()
