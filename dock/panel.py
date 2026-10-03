from __future__ import annotations

import math
from dataclasses import replace
from typing import Callable

from PySide6.QtCore import (
    QEasingCurve,
    QPoint,
    QPointF,
    QPropertyAnimation,
    QRect,
    QSize,
    Qt,
    QTimer,
    QVariantAnimation,
)
from PySide6.QtGui import QColor, QGuiApplication, QPainter, QPainterPath, QPen
from PySide6.QtWidgets import (
    QApplication,
    QBoxLayout,
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

from .config import DockConfig
from .geometry import (
    BAR,
    FLARE,
    GRIP,
    ICON,
    ICON_GAP,
    PANEL_HEIGHT,
    Rect,
    bar_length,
    bar_rect,
    expanded_rect,
    is_vertical,
    snap,
)
from .liquid import droplet_path, paint_liquid
from .icons import svg_icon
from .registry import LoadedTool
from .tool import Tool

DRAG_THRESHOLD = 4
QT_MAX = 16777215
EXPANDED_RADIUS = 22
WOBBLE_PX = 6.0  # amplitud máxima de la onda líquida
HOVER_JIGGLE = 0.4

STYLE = """
QWidget { color: #f0f4f8; font-family: 'Segoe UI'; font-size: 13px; background: transparent; }
QToolButton#appIcon { border: none; border-radius: 15px; font-size: 14px; font-weight: 600; }
QToolButton#appIcon:hover { background: rgba(255, 255, 255, 46); }
QToolButton#appIcon:checked { background: rgba(255, 255, 255, 70); border: 1px solid rgba(255, 255, 255, 120); }
QLabel#panelTitle { font-size: 14px; font-weight: 600; }
QPushButton#headerButton { background: transparent; border: none; border-radius: 10px; padding: 2px 7px;
                           font-size: 13px; }
QPushButton#headerButton:hover { background: rgba(255, 255, 255, 46); }
QPushButton#headerButton:checked { background: rgba(255, 255, 255, 80); }
QFrame#card { background: rgba(255, 255, 255, 16); border: 1px solid rgba(255, 255, 255, 34); border-radius: 14px; }
QLabel#cardError { color: #ff7b72; }
QPushButton { background: rgba(255, 255, 255, 34); border: 1px solid rgba(255, 255, 255, 60);
              border-radius: 12px; padding: 6px 10px; }
QPushButton:hover { background: rgba(255, 255, 255, 56); }
QPushButton:disabled { color: #8b949e; }
QPushButton[active="true"] { background: rgba(120, 190, 255, 90); border-color: rgba(170, 215, 255, 220); }
QProgressBar { background: rgba(255, 255, 255, 26); border: none; border-radius: 7px;
               text-align: center; font-size: 11px; min-height: 16px; }
QProgressBar::chunk { background: rgba(63, 185, 80, 210); border-radius: 7px; }
QProgressBar[level="warn"]::chunk { background: rgba(210, 153, 34, 220); }
QProgressBar[level="high"]::chunk { background: rgba(248, 81, 73, 220); }
"""


class Grip(QWidget):
    """Agarre para arrastrar la barra: puntos dibujados, cursor de mover.

    No consume los clics: el evento sube hasta Panel, que maneja el arrastre.
    """

    SPACING, RADIUS = 5, 1.6

    def __init__(self):
        super().__init__()
        self.vertical = True
        self.setCursor(Qt.CursorShape.SizeAllCursor)
        self.setToolTip("Arrastrá para mover · clic derecho para el menú")
        self.setAttribute(Qt.WidgetAttribute.WA_Hover)
        self.set_vertical(True)

    def set_vertical(self, vertical: bool) -> None:
        self.vertical = vertical
        self.setMinimumSize(0, 0)
        self.setMaximumSize(QT_MAX, QT_MAX)
        if vertical:
            self.setFixedSize(ICON, GRIP)
        else:
            self.setFixedSize(GRIP, ICON)
        self.update()

    def _grid(self) -> tuple[int, int]:
        return (2, 3) if self.vertical else (3, 2)

    def dots(self) -> int:
        columns, rows = self._grid()
        return columns * rows

    def paintEvent(self, event) -> None:
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)
        painter.setPen(Qt.PenStyle.NoPen)
        painter.setBrush(QColor(255, 255, 255, 230) if self.underMouse() else QColor(255, 255, 255, 140))
        columns, rows = self._grid()
        left = (self.width() - (columns - 1) * self.SPACING) / 2
        top = (self.height() - (rows - 1) * self.SPACING) / 2
        for column in range(columns):
            for row in range(rows):
                center = QPointF(left + column * self.SPACING, top + row * self.SPACING)
                painter.drawEllipse(center, self.RADIUS, self.RADIUS)


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
    """Gota de vidrio pegada a un borde (izquierdo, derecho o superior) con un ícono por app.

    Clic en un ícono despliega esa app hacia adentro de la pantalla.
    """

    def __init__(
        self,
        config: DockConfig,
        loaded: list[LoadedTool],
        screen_area: Callable[[], Rect],
        animation_ms: int = 260,
        hide_delay_ms: int = 700,
        panel_height: int = PANEL_HEIGHT,
        fit_content: bool = True,
        on_config_change: Callable[[DockConfig], None] = lambda config: None,
        on_close: Callable[[], None] | None = None,
        on_settings: Callable[[], None] = lambda: None,
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
        self.on_settings = on_settings
        self.revealed = False
        self.wobble = 0.0
        self._phase = 0.0
        self.wobble_ms = 650
        self.dragging = False
        self._press_global: QPoint | None = None
        self._press_offset = QPoint()
        self._path = QPainterPath()
        self.current: str | None = None
        self.cards: dict[str, Card] = {}
        self.tool_buttons: dict[str, QToolButton] = {}
        self._titles: dict[str, str] = {}
        self.timers: list[QTimer] = []
        self.bar_len = bar_length(len(loaded))

        self.bar = self._build_bar()
        self.flyout = self._build_flyout()
        for item in loaded:
            self._add_tool(item)
        self.bar.layout().addStretch(1)
        self.settings_button = QToolButton()
        self.settings_button.setObjectName("appIcon")
        self.settings_button.setToolTip("Configuración")
        self.settings_button.setFixedSize(22, 22)
        gear = svg_icon("settings", color="#aab4c0", size=15)
        if gear is not None:
            self.settings_button.setIcon(gear)
            self.settings_button.setIconSize(QSize(15, 15))
        else:
            self.settings_button.setText("⚙")
        self.settings_button.clicked.connect(lambda: self.on_settings())
        self.bar.layout().addWidget(self.settings_button, 0, Qt.AlignmentFlag.AlignCenter)

        root = QBoxLayout(QBoxLayout.Direction.LeftToRight, self)
        root.setSizeConstraint(QLayout.SizeConstraint.SetNoConstraint)
        root.setContentsMargins(0, 0, 0, 0)
        root.setSpacing(0)
        self._arrange()

        self.hide_timer = QTimer(self)
        self.hide_timer.setSingleShot(True)
        self.hide_timer.setInterval(hide_delay_ms)
        self.hide_timer.timeout.connect(self.conceal)
        self.animation = QPropertyAnimation(self, b"geometry", self)
        self.animation.finished.connect(self._after_animation)
        self.wobble_anim = QVariantAnimation(self)
        self.wobble_anim.setEasingCurve(QEasingCurve.Type.OutCubic)
        self.wobble_anim.valueChanged.connect(self._on_wobble)

        self.flyout.setVisible(False)
        self.setGeometry(QRect(*self._target(False)))
        self._update_shape()
        if config.pinned and self.cards:
            self.reveal()

    # --- construcción -----------------------------------------------------------------------

    def _build_bar(self) -> QWidget:
        bar = QWidget()
        layout = QBoxLayout(QBoxLayout.Direction.TopToBottom, bar)
        layout.setSpacing(ICON_GAP)
        self.grip = Grip()
        layout.addWidget(self.grip, 0, Qt.AlignmentFlag.AlignCenter)
        return bar

    def _build_flyout(self) -> QWidget:
        flyout = QWidget()
        layout = QVBoxLayout(flyout)
        header = QHBoxLayout()
        self.title = QLabel("")
        self.title.setObjectName("panelTitle")
        self.pin_button = self._header_button("pin", "📌")
        self.pin_button.setCheckable(True)
        self.pin_button.setChecked(self.config.pinned)
        self.pin_button.setToolTip("Fijar panel abierto")
        self.pin_button.clicked.connect(self.toggle_pin)
        self.close_button = self._header_button("x", "✕")
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

    @staticmethod
    def _header_button(icon_name: str, fallback: str) -> QPushButton:
        icon = svg_icon(icon_name, size=15)
        button = QPushButton("" if icon else fallback)
        if icon:
            button.setIcon(icon)
            button.setIconSize(QSize(15, 15))
        button.setObjectName("headerButton")
        return button

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
        svg = svg_icon(icon, size=18)
        if svg is not None:
            button.setIcon(svg)
            button.setIconSize(QSize(18, 18))
        else:
            button.setText(icon)
        button.setToolTip(title)
        button.setCheckable(True)
        button.setFixedSize(ICON, ICON)
        button.clicked.connect(lambda _checked=False, name=item.name: self._icon_clicked(name))
        self.tool_buttons[item.name] = button
        self.bar.layout().addWidget(button, 0, Qt.AlignmentFlag.AlignCenter)

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
        """Orienta barra y app según el borde: la barra queda pegada al borde y la app hacia adentro."""
        edge = self.config.edge
        vertical = is_vertical(edge)
        root: QBoxLayout = self.layout()
        root.removeWidget(self.bar)
        root.removeWidget(self.flyout)
        bar_layout: QBoxLayout = self.bar.layout()
        side = (BAR - ICON) // 2
        for widget in (self.bar, self.flyout):
            widget.setMinimumSize(0, 0)
            widget.setMaximumSize(QT_MAX, QT_MAX)
        if vertical:
            root.setDirection(QBoxLayout.Direction.LeftToRight)
            order = (self.flyout, self.bar) if edge == "right" else (self.bar, self.flyout)
            bar_layout.setDirection(QBoxLayout.Direction.TopToBottom)
            bar_layout.setContentsMargins(side, FLARE, side, FLARE + 4)
            self.bar.setFixedWidth(BAR)
            self.flyout.setFixedWidth(self.config.width)
            self.flyout.layout().setContentsMargins(14, 8 + FLARE, 10, 12 + FLARE)
        else:
            root.setDirection(QBoxLayout.Direction.TopToBottom)
            order = (self.bar, self.flyout)
            bar_layout.setDirection(QBoxLayout.Direction.LeftToRight)
            bar_layout.setContentsMargins(FLARE + 4, side, FLARE, side)
            self.bar.setFixedHeight(BAR)
            self.flyout.layout().setContentsMargins(14 + FLARE, 4, 10 + FLARE, 14)
        self.grip.set_vertical(vertical)
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

    # --- geometría, forma y animación -------------------------------------------------------

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
            return expanded_rect(area, self.config.edge, self.config.position, self.bar_len,
                                 self.config.width, self._content_height())
        return bar_rect(area, self.config.edge, self.config.position, self.bar_len)

    def _move_to(self, revealed: bool) -> None:
        self.revealed = revealed
        if revealed:
            self.flyout.setVisible(True)
        target = QRect(*self._target(revealed))
        self.animation.stop()
        # Al abrir, un rebote leve da la sensación de líquido; al cerrar, se recoge sin rebote.
        curve = QEasingCurve(QEasingCurve.Type.OutBack if revealed else QEasingCurve.Type.InOutCubic)
        if revealed:
            curve.setOvershoot(1.1)
        self.animation.setEasingCurve(curve)
        if self.animation_ms <= 0 or not self.isVisible():
            self.setGeometry(target)
            self._after_animation()
            return
        self.animation.setDuration(self.animation_ms)
        self.animation.setStartValue(self.geometry())
        self.animation.setEndValue(target)
        self.animation.start()
        self.jiggle(1.0)

    def _after_animation(self) -> None:
        if not self.revealed:
            self.flyout.setVisible(False)
        self._update_shape()
        self.update()

    def apply_config(self, config: DockConfig) -> None:
        """Aplica cambios de Configuración en vivo (borde, ancho, fijado, efecto líquido)."""
        self.config = config
        self.pin_button.setChecked(config.pinned)
        self._arrange()
        self.animation.stop()
        self.setGeometry(QRect(*self._target(self.revealed)))
        self._update_shape()
        self.update()

    def jiggle(self, strength: float = 1.0) -> None:
        """Onda líquida que se amortigua: la gota tiembla y vuelve a su forma."""
        if not self.config.liquid or not self.isVisible() or self.wobble_ms <= 0:
            return
        self.wobble_anim.stop()
        self.wobble_anim.setDuration(self.wobble_ms)
        self.wobble_anim.setStartValue(float(strength))
        self.wobble_anim.setEndValue(0.0)
        self.wobble_anim.start()

    def _on_wobble(self, value) -> None:
        value = float(value)
        self.wobble = value * WOBBLE_PX
        self._phase = (1.0 - value) * 4 * math.pi
        self._update_shape()
        self.update()

    def _update_shape(self) -> None:
        # Sin setMask: la máscara de Windows es dentada; los píxeles transparentes ya dejan pasar los clics.
        radius = EXPANDED_RADIUS if self.revealed else BAR / 2
        self._path = droplet_path(self.width(), self.height(), self.config.edge, radius, FLARE,
                                  wobble=self.wobble, phase=self._phase)

    def resizeEvent(self, event) -> None:
        super().resizeEvent(event)
        self._update_shape()

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
        edge, position = snap(self._area(), self.x(), self.y(), self.width(), self.height())
        self._save(edge=edge, position=position)
        self._arrange()
        self._move_to(False)

    # --- eventos ----------------------------------------------------------------------------

    def build_menu(self) -> QMenu:
        menu = QMenu(self)
        settings = menu.addAction("Configuración")
        settings.triggered.connect(lambda: self.on_settings())
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
        if self.wobble_anim.state() != QVariantAnimation.State.Running:
            self.jiggle(HOVER_JIGGLE)
        super().enterEvent(event)

    def leaveEvent(self, event) -> None:
        if self.revealed and not self.config.pinned:
            self.hide_timer.start()
        super().leaveEvent(event)

    def paintEvent(self, event) -> None:
        painter = QPainter(self)
        paint_liquid(painter, self._path)
        if self.revealed:
            painter.setRenderHint(QPainter.RenderHint.Antialiasing)
            painter.setPen(QPen(QColor(255, 255, 255, 40), 1))
            bar = self.bar.geometry()
            if self.config.edge == "top":
                painter.drawLine(16, bar.bottom(), self.width() - 16, bar.bottom())
            else:
                x = bar.left() if self.config.edge == "right" else bar.right()
                painter.drawLine(x, 16, x, self.height() - 16)


def primary_area() -> Rect:
    geometry = QGuiApplication.primaryScreen().availableGeometry()
    return geometry.x(), geometry.y(), geometry.width(), geometry.height()
