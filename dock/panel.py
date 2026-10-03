from __future__ import annotations

from typing import Callable

from PySide6.QtCore import QEasingCurve, QPropertyAnimation, QRect, Qt, QTimer
from PySide6.QtGui import QColor, QGuiApplication, QPainter
from PySide6.QtWidgets import QFrame, QLabel, QLayout, QScrollArea, QVBoxLayout, QWidget

from .backdrop import apply_backdrop
from .config import DockConfig
from .geometry import Rect, panel_rect
from .registry import LoadedTool
from .tool import Tool

STYLE = """
QWidget { color: #e6edf3; font-family: 'Segoe UI'; font-size: 13px; background: transparent; }
QFrame#card { background: rgba(255, 255, 255, 18); border: 1px solid rgba(255, 255, 255, 28); border-radius: 12px; }
QLabel#cardTitle { font-size: 12px; font-weight: 600; color: #9da7b3; text-transform: uppercase; }
QLabel#cardError { color: #f85149; }
QPushButton { background: rgba(255, 255, 255, 30); border: 1px solid rgba(255, 255, 255, 40);
              border-radius: 8px; padding: 6px 10px; }
QPushButton:hover { background: rgba(255, 255, 255, 50); }
QPushButton:disabled { color: #6e7681; }
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
    def __init__(
        self,
        config: DockConfig,
        loaded: list[LoadedTool],
        screen_area: Callable[[], Rect],
        animation_ms: int = 220,
        hide_delay_ms: int = 700,
    ):
        super().__init__(None, Qt.WindowType.FramelessWindowHint | Qt.WindowType.Tool
                         | Qt.WindowType.WindowStaysOnTopHint)
        self.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground)
        self.setMinimumSize(1, 1)
        self.setStyleSheet(STYLE)
        self.config = config
        self._area = screen_area
        self.animation_ms = animation_ms
        self.revealed = False
        self.backdrop_active = False
        self.cards: dict[str, Card] = {}
        self.timers: list[QTimer] = []

        outer = QVBoxLayout(self)
        outer.setSizeConstraint(QLayout.SizeConstraint.SetNoConstraint)
        outer.setContentsMargins(14, 14, 14, 14)
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
        outer.addWidget(self.scroll)

        self.hide_timer = QTimer(self)
        self.hide_timer.setSingleShot(True)
        self.hide_timer.setInterval(hide_delay_ms)
        self.hide_timer.timeout.connect(self.conceal)
        self.animation = QPropertyAnimation(self, b"geometry", self)
        self.animation.setEasingCurve(QEasingCurve.Type.OutCubic)
        self.animation.finished.connect(self._after_animation)

        self.scroll.setVisible(False)
        self.setGeometry(QRect(*self._target(False)))

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

    def _target(self, revealed: bool) -> Rect:
        return panel_rect(self._area(), self.config.edge, self.config.width, revealed)

    def _move_to(self, revealed: bool) -> None:
        self.revealed = revealed
        if revealed:
            self.scroll.setVisible(True)
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
            self.scroll.setVisible(False)
        self.update()

    def reveal(self) -> None:
        self.hide_timer.stop()
        if not self.revealed:
            self._move_to(True)

    def conceal(self) -> None:
        if self.revealed:
            self._move_to(False)

    def reposition(self, *_args) -> None:
        self.animation.stop()
        self.setGeometry(QRect(*self._target(self.revealed)))

    def enterEvent(self, event) -> None:
        self.reveal()
        super().enterEvent(event)

    def leaveEvent(self, event) -> None:
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
        if not self.revealed:
            painter.setBrush(QColor(88, 166, 255, 170))
        elif self.backdrop_active:
            painter.setBrush(QColor(16, 18, 24, 110))
        else:
            painter.setBrush(QColor(22, 24, 30, 235))
        painter.drawRoundedRect(self.rect(), 12, 12)


def primary_area() -> Rect:
    geometry = QGuiApplication.primaryScreen().availableGeometry()
    return geometry.x(), geometry.y(), geometry.width(), geometry.height()
