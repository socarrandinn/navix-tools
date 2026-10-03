from __future__ import annotations

from dataclasses import replace
from typing import Callable

from PySide6.QtCore import QEasingCurve, QPoint, QPropertyAnimation, QRect, Qt, QTimer
from PySide6.QtGui import QColor, QFont, QGuiApplication, QPainter
from PySide6.QtWidgets import (
    QApplication,
    QFrame,
    QHBoxLayout,
    QLabel,
    QLayout,
    QMenu,
    QPushButton,
    QScrollArea,
    QVBoxLayout,
    QWidget,
)

from .backdrop import apply_backdrop
from .config import DockConfig
from .geometry import PANEL_HEIGHT, Rect, bubble_rect, expanded_rect, snap
from .registry import LoadedTool
from .tool import Tool

DRAG_THRESHOLD = 4
ACCENT = QColor(88, 166, 255)

STYLE = """
QWidget { color: #e6edf3; font-family: 'Segoe UI'; font-size: 13px; background: transparent; }
QLabel#panelTitle { font-size: 14px; font-weight: 600; }
QPushButton#headerButton { background: transparent; border: none; border-radius: 6px; padding: 2px 6px;
                           font-size: 14px; }
QPushButton#headerButton:hover { background: rgba(255, 255, 255, 40); }
QPushButton#headerButton:checked { background: rgba(88, 166, 255, 90); }
QFrame#card { background: rgba(255, 255, 255, 18); border: 1px solid rgba(255, 255, 255, 28); border-radius: 12px; }
QLabel#cardTitle { font-size: 12px; font-weight: 600; color: #9da7b3; text-transform: uppercase; }
QLabel#cardError { color: #f85149; }
QPushButton { background: rgba(255, 255, 255, 30); border: 1px solid rgba(255, 255, 255, 40);
              border-radius: 8px; padding: 6px 10px; }
QPushButton:hover { background: rgba(255, 255, 255, 50); }
QPushButton:disabled { color: #6e7681; }
QPushButton[active="true"] { background: rgba(88, 166, 255, 70); border-color: #58a6ff; }
QProgressBar { background: rgba(255, 255, 255, 20); border: none; border-radius: 4px; height: 8px;
               text-align: right; font-size: 11px; }
QProgressBar::chunk { background: #58a6ff; border-radius: 4px; }
QScrollArea { border: none; }
"""


class Card(QFrame):
    def __init__(self, title: str, body: QWidget | None, error: str | None = None):
        super().__init__()
        self.setObjectName("card")
        layout = QVBoxLayout(self)
        layout.setContentsMargins(12, 10, 12, 10)
        header = QLabel(title)
        header.setObjectName("cardTitle")
        layout.addWidget(header)
        if body is not None:
            layout.addWidget(body)
        self.error_label = QLabel("")
        self.error_label.setObjectName("cardError")
        self.error_label.setWordWrap(True)
        layout.addWidget(self.error_label)
        self.show_error(error or "")

    def show_error(self, text: str) -> None:
        self.error_label.setText(text)
        self.error_label.setVisible(bool(text))


class Panel(QWidget):
    """Círculo de 50 px pegado a un borde que se expande en un panel con herramientas."""

    def __init__(
        self,
        config: DockConfig,
        loaded: list[LoadedTool],
        screen_area: Callable[[], Rect],
        animation_ms: int = 220,
        hide_delay_ms: int = 700,
        hover_delay_ms: int = 350,
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
        self.setToolTip("IPDock: pasá el mouse para abrir, arrastrá para mover, clic derecho para el menú")
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
        self.cards: dict[str, Card] = {}
        self.timers: list[QTimer] = []

        outer = QVBoxLayout(self)
        outer.setSizeConstraint(QLayout.SizeConstraint.SetNoConstraint)
        outer.setContentsMargins(14, 10, 14, 14)
        self.body = QWidget()
        body_layout = QVBoxLayout(self.body)
        body_layout.setContentsMargins(0, 0, 0, 0)
        self.header = self._build_header()
        body_layout.addLayout(self.header)
        self.scroll = QScrollArea()
        self.scroll.setWidgetResizable(True)
        self.scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        content = QWidget()
        cards_layout = QVBoxLayout(content)
        cards_layout.setContentsMargins(0, 0, 0, 0)
        cards_layout.setSpacing(10)
        if not loaded:
            cards_layout.addWidget(QLabel("Sin herramientas. Edita dock.json."))
        for item in loaded:
            card = self._build_card(item)
            self.cards[item.name] = card
            cards_layout.addWidget(card)
        cards_layout.addStretch(1)
        self.scroll.setWidget(content)
        body_layout.addWidget(self.scroll)
        outer.addWidget(self.body)

        self.hide_timer = self._single_shot(hide_delay_ms, self.conceal)
        self.hover_timer = self._single_shot(hover_delay_ms, self.reveal)
        self.animation = QPropertyAnimation(self, b"geometry", self)
        self.animation.setEasingCurve(QEasingCurve.Type.OutCubic)
        self.animation.finished.connect(self._after_animation)

        self.revealed = config.pinned
        self.body.setVisible(self.revealed)
        self.setGeometry(QRect(*self._target(self.revealed)))

    def _single_shot(self, interval: int, slot: Callable[[], None]) -> QTimer:
        timer = QTimer(self)
        timer.setSingleShot(True)
        timer.setInterval(interval)
        timer.timeout.connect(slot)
        return timer

    def _build_header(self) -> QHBoxLayout:
        header = QHBoxLayout()
        title = QLabel("IPDock")
        title.setObjectName("panelTitle")
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
        header.addWidget(title)
        header.addStretch(1)
        header.addWidget(self.pin_button)
        header.addWidget(self.close_button)
        return header

    def _build_card(self, item: LoadedTool) -> Card:
        if item.tool is None:
            return Card(item.name, None, item.error)
        tool = item.tool
        try:
            body = tool.create_widget()
        except Exception as exc:  # noqa: BLE001
            return Card(tool.title or item.name, None, f"{type(exc).__name__}: {exc}")
        card = Card(tool.title or item.name, body)
        self._safe_refresh(tool, card)
        if tool.refresh_ms > 0:
            timer = QTimer(self)
            timer.setInterval(tool.refresh_ms)
            timer.timeout.connect(lambda t=tool, c=card: self._safe_refresh(t, c))
            timer.start()
            self.timers.append(timer)
        return card

    @staticmethod
    def _safe_refresh(tool: Tool, card: Card) -> None:
        try:
            tool.refresh()
        except Exception as exc:  # noqa: BLE001
            card.show_error(f"Error al refrescar: {exc}")

    # --- geometría y animación -------------------------------------------------------------

    def _target(self, revealed: bool) -> Rect:
        area = self._area()
        if revealed:
            return expanded_rect(area, self.config.edge, self.config.width, self.config.position,
                                 height=self._expanded_height())
        return bubble_rect(area, self.config.edge, self.config.position)

    def _expanded_height(self) -> int:
        if not self.fit_content:
            return self.panel_height
        margins = self.layout().contentsMargins()
        needed = (
            margins.top() + margins.bottom()
            + self.header.sizeHint().height()
            + self.body.layout().spacing()
            + self.scroll.widget().sizeHint().height()
            + 4
        )
        return min(self.panel_height, needed)

    def _move_to(self, revealed: bool) -> None:
        self.revealed = revealed
        if revealed:
            self.body.setVisible(True)
        self._update_backdrop()
        target = QRect(*self._target(revealed))
        self.animation.stop()
        if self.animation_ms <= 0:
            self.setGeometry(target)
            self._after_animation()
            return
        self.animation.setDuration(self.animation_ms)
        self.animation.setStartValue(self.geometry())
        self.animation.setEndValue(target)
        self.animation.start()

    def _after_animation(self) -> None:
        if not self.revealed:
            self.body.setVisible(False)
        self.update()

    def _update_backdrop(self) -> None:
        if self.config.backdrop != "acrylic" or not self.testAttribute(Qt.WidgetAttribute.WA_WState_Created):
            self.backdrop_active = False
            return
        applied = apply_backdrop(int(self.winId()), enabled=self.revealed)
        self.backdrop_active = applied and self.revealed

    def reveal(self) -> None:
        self.hide_timer.stop()
        self.hover_timer.stop()
        if not self.revealed:
            self._move_to(True)

    def conceal(self) -> None:
        if self.revealed and not self.config.pinned:
            self._move_to(False)

    def reposition(self, *_args) -> None:
        self.animation.stop()
        self.setGeometry(QRect(*self._target(self.revealed)))

    def _save(self, **changes) -> None:
        self.config = replace(self.config, **changes)
        self.on_config_change(self.config)

    def toggle_pin(self) -> None:
        self._save(pinned=not self.config.pinned)
        self.pin_button.setChecked(self.config.pinned)
        if self.config.pinned:
            self.reveal()

    # --- arrastre del círculo ----------------------------------------------------------------

    def begin_drag(self, global_pos: QPoint) -> None:
        self.hover_timer.stop()
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
            self.reveal()
            return
        edge, position = snap(self._area(), self.x(), self.y())
        self._save(edge=edge, position=position)
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
        if not self.revealed and event.button() == Qt.MouseButton.LeftButton:
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
        if not self.revealed and self._press_global is None:
            self.hover_timer.start()
        super().enterEvent(event)

    def leaveEvent(self, event) -> None:
        self.hover_timer.stop()
        if self.revealed and not self.config.pinned:
            self.hide_timer.start()
        super().leaveEvent(event)

    def showEvent(self, event) -> None:
        super().showEvent(event)
        self._update_backdrop()

    def paintEvent(self, event) -> None:
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)
        painter.setPen(Qt.PenStyle.NoPen)
        if not self.revealed and not self.animation.state() == QPropertyAnimation.State.Running:
            painter.setBrush(ACCENT)
            painter.drawEllipse(self.rect().adjusted(1, 1, -1, -1))
            painter.setPen(QColor(255, 255, 255))
            painter.setFont(QFont("Segoe UI", 11, QFont.Weight.Bold))
            painter.drawText(self.rect(), Qt.AlignmentFlag.AlignCenter, "IP")
            return
        if self.backdrop_active:
            painter.setBrush(QColor(16, 18, 24, 110))
        else:
            painter.setBrush(QColor(22, 24, 30, 235))
        painter.drawRoundedRect(self.rect(), 14, 14)


def primary_area() -> Rect:
    geometry = QGuiApplication.primaryScreen().availableGeometry()
    return geometry.x(), geometry.y(), geometry.width(), geometry.height()
