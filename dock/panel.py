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
    QRectF,
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
    QGraphicsOpacityEffect,
    QHBoxLayout,
    QLabel,
    QLayout,
    QMenu,
    QPushButton,
    QSizePolicy,
    QSpacerItem,
    QStackedWidget,
    QToolButton,
    QVBoxLayout,
    QWidget,
)

from .config import DockConfig
from .geometry import (
    BAR,
    FLARE,
    GAP,
    GRIP,
    ICON,
    ICON_GAP,
    MARGIN,
    PANEL_HEIGHT,
    Rect,
    bar_length,
    bar_rect,
    expanded_rect,
    is_vertical,
    snap,
    stretched_rect,
)
from .liquid import bridge_path, droplet_path, paint_liquid
from .icons import svg_icon
from .registry import LoadedTool
from .tool import Tool

DRAG_THRESHOLD = 4
QT_MAX = 16777215
EXPANDED_RADIUS = 22
WOBBLE_PX = 6.0  # amplitud máxima de la onda líquida
HOVER_JIGGLE = 0.4
DETACH_DISTANCE = 70  # px que hay que tirar hacia adentro para despegar la gota
PULL_GAIN = 0.6       # cuánto se estira la gota por cada px de tirón

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
        layout.setContentsMargins(16, 14, 16, 14)
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
    """Gota líquida pegada a un borde (izquierdo, derecho o superior) con un ícono por app.

    Clic en un ícono hace brotar la app de la barra como una gota que se separa. Al arrastrar,
    la barra se estira como líquido y se despega del borde pasado un umbral.
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
        self.bud = 0.0          # 0 = solo barra, 1 = app separada como gota propia
        self.wobble = 0.0
        self._phase = 0.0
        self.wobble_ms = 650
        self.dragging = False
        self.detached = False
        self._pull = 0.0
        self._drag_position = config.position
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

        # La barra vive en una columna con un espaciador: así, con la app abierta, la barra
        # mantiene su tamaño y su lugar aunque la ventana se haya corrido para entrar en pantalla.
        self.bar_column = QWidget()
        column = QBoxLayout(QBoxLayout.Direction.TopToBottom, self.bar_column)
        column.setContentsMargins(0, 0, 0, 0)
        column.setSpacing(0)
        self._bar_spacer = QSpacerItem(0, 0, QSizePolicy.Policy.Fixed, QSizePolicy.Policy.Fixed)
        column.addSpacerItem(self._bar_spacer)
        column.addWidget(self.bar)
        column.addStretch(1)

        self._opacity = QGraphicsOpacityEffect(self.flyout)
        self.flyout.setGraphicsEffect(self._opacity)

        root = QBoxLayout(QBoxLayout.Direction.LeftToRight, self)
        root.setSizeConstraint(QLayout.SizeConstraint.SetNoConstraint)
        root.setContentsMargins(0, 0, 0, 0)
        root.setSpacing(GAP)
        self._arrange()

        self.hide_timer = QTimer(self)
        self.hide_timer.setSingleShot(True)
        self.hide_timer.setInterval(hide_delay_ms)
        self.hide_timer.timeout.connect(self.conceal)
        self.animation = QPropertyAnimation(self, b"geometry", self)
        self.animation.setEasingCurve(QEasingCurve(QEasingCurve.Type.OutBack))
        self.animation.finished.connect(self._refresh_shape)
        self.bud_anim = QVariantAnimation(self)
        self.bud_anim.valueChanged.connect(lambda value: self.set_bud(float(value)))
        self.bud_anim.finished.connect(self._bud_finished)
        self.wobble_anim = QVariantAnimation(self)
        self.wobble_anim.setEasingCurve(QEasingCurve.Type.OutCubic)
        self.wobble_anim.valueChanged.connect(self._on_wobble)

        self.flyout.setVisible(False)
        self._set_rect(self._target(False))
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
        root.removeWidget(self.bar_column)
        root.removeWidget(self.flyout)
        bar_layout: QBoxLayout = self.bar.layout()
        column: QBoxLayout = self.bar_column.layout()
        side = (BAR - ICON) // 2
        for widget in (self.bar, self.bar_column, self.flyout):
            widget.setMinimumSize(0, 0)
            widget.setMaximumSize(QT_MAX, QT_MAX)
        if vertical:
            root.setDirection(QBoxLayout.Direction.LeftToRight)
            order = (self.flyout, self.bar_column) if edge == "right" else (self.bar_column, self.flyout)
            column.setDirection(QBoxLayout.Direction.TopToBottom)
            bar_layout.setDirection(QBoxLayout.Direction.TopToBottom)
            bar_layout.setContentsMargins(side, FLARE + 4, side, FLARE + 6)
            self.bar.setFixedSize(BAR, self.bar_len)
            self.bar_column.setFixedWidth(BAR)
            self.flyout.setFixedWidth(self.config.width)
            self.flyout.layout().setContentsMargins(22, 16, 20, 18)
        else:
            root.setDirection(QBoxLayout.Direction.TopToBottom)
            order = (self.bar_column, self.flyout)
            column.setDirection(QBoxLayout.Direction.LeftToRight)
            bar_layout.setDirection(QBoxLayout.Direction.LeftToRight)
            bar_layout.setContentsMargins(FLARE + 6, side, FLARE + 4, side)
            self.bar.setFixedSize(self.bar_len, BAR)
            self.bar_column.setFixedHeight(BAR)
            self.flyout.layout().setContentsMargins(22, 16, 20, 18)
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
        opening = not self.revealed
        self.revealed = True
        self.flyout.setVisible(True)
        self.animation.stop()
        self._set_rect(self._target(True))
        if opening or self.bud < 1.0:
            self._animate_bud(1.0)
            self.jiggle(1.0)
        self._sync_buttons()

    def reveal(self) -> None:
        if self.cards:
            self.open_tool(self.current or next(iter(self.cards)))

    def conceal(self) -> None:
        if self.revealed and not self.config.pinned:
            self.revealed = False
            self._animate_bud(0.0)
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

    # --- brote: la app sale de la barra como una gota que se separa ------------------------

    def _animate_bud(self, target: float) -> None:
        self.bud_anim.stop()
        if self.animation_ms <= 0 or not self.isVisible():
            self.set_bud(target)
            self._bud_finished()
            return
        self.bud_anim.setDuration(round(self.animation_ms * 1.8))
        self.bud_anim.setStartValue(self.bud)
        self.bud_anim.setEndValue(target)
        self.bud_anim.start()

    def set_bud(self, value: float) -> None:
        self.bud = max(0.0, min(1.0, value))
        self._opacity.setOpacity(self.flyout_opacity())
        self._refresh_shape()

    def flyout_opacity(self) -> float:
        # El contenido aparece recién cuando la gota ya casi se separó.
        return max(0.0, min(1.0, (self.bud - 0.55) / 0.4))

    def _bud_finished(self) -> None:
        if not self.revealed and self.bud == 0.0:
            self.flyout.setVisible(False)
            self._set_rect(self._target(False))
        self._refresh_shape()

    # --- geometría y forma ------------------------------------------------------------------

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

    def _set_rect(self, rect: Rect) -> None:
        self.setGeometry(QRect(*rect))
        self._sync_bar_offset()
        self._refresh_shape()

    def _sync_bar_offset(self) -> None:
        """Con la app abierta, corre la barra dentro de la ventana para que quede donde estaba."""
        offset = 0
        if not self.flyout.isHidden():
            bx, by, _, _ = bar_rect(self._area(), self.config.edge, self.config.position, self.bar_len)
            offset = max(0, (by - self.y()) if is_vertical(self.config.edge) else (bx - self.x()))
        if is_vertical(self.config.edge):
            self._bar_spacer.changeSize(0, offset, QSizePolicy.Policy.Fixed, QSizePolicy.Policy.Fixed)
        else:
            self._bar_spacer.changeSize(offset, 0, QSizePolicy.Policy.Fixed, QSizePolicy.Policy.Fixed)
        self.bar_column.layout().invalidate()
        self.layout().activate()
        self.bar_column.layout().activate()

    def bar_shape_rect(self) -> QRectF:
        """Rectángulo de la barra en coordenadas de la ventana."""
        if self.flyout.isHidden():
            return QRectF(0, 0, self.width(), self.height())
        top_left = self.bar.mapTo(self, QPoint(0, 0))
        return QRectF(top_left.x(), top_left.y(), self.bar.width(), self.bar.height())

    def shape(self) -> QPainterPath:
        return self._path

    def _refresh_shape(self) -> None:
        self._update_shape()
        self.update()

    def _update_shape(self) -> None:
        # Sin setMask: la máscara de Windows es dentada; los píxeles transparentes ya dejan pasar los clics.
        edge = self.config.edge
        width, height = self.width(), self.height()
        if self.detached:
            path = QPainterPath()
            radius = min(width, height) / 2
            path.addRoundedRect(QRectF(0, 0, width, height), radius, radius)
            self._path = path
            return
        if self._pull > 0:
            self._path = self._stretched_path(width, height)
            return
        if self.flyout.isHidden():
            self._path = droplet_path(width, height, edge, BAR / 2, FLARE, wobble=self.wobble, phase=self._phase)
            return
        bar = self.bar_shape_rect()
        path = droplet_path(bar.width(), bar.height(), edge, BAR / 2, FLARE,
                            wobble=self.wobble, phase=self._phase).translated(bar.topLeft())
        growth = QEasingCurve(QEasingCurve.Type.OutBack).valueForProgress(self.bud)
        if growth > 0.01:
            blob = self._blob_rect(bar, QRectF(self.flyout.geometry()), growth)
            radius = min(EXPANDED_RADIUS, blob.width() / 2, blob.height() / 2)
            body = QPainterPath()
            body.addRoundedRect(blob, radius, radius)
            neck = bridge_path(bar, blob, horizontal=is_vertical(edge), thickness=self._neck_thickness())
            path = path.united(body).united(neck)
        self._path = path

    def _neck_thickness(self) -> float:
        # Grueso al principio; se afina y se corta cuando la gota ya casi terminó de salir.
        t = max(0.0, min(1.0, (self.bud - 0.5) / 0.38))
        return self.bar_len * 0.55 * (1.0 - t * t * (3 - 2 * t))

    def _blob_rect(self, bar: QRectF, final: QRectF, growth: float) -> QRectF:
        growth = min(growth, 1.05)
        minimum = BAR * 0.6
        width = max(minimum, final.width() * growth)
        height = max(minimum, final.height() * growth)
        edge = self.config.edge
        if is_vertical(edge):
            cy = bar.center().y() + (final.center().y() - bar.center().y()) * min(1.0, growth)
            x = final.right() - width if edge == "right" else final.left()
            rect = QRectF(x, cy - height / 2, width, height)
        else:
            cx = bar.center().x() + (final.center().x() - bar.center().x()) * min(1.0, growth)
            rect = QRectF(cx - width / 2, final.top(), width, height)
        return rect.intersected(QRectF(0, 0, self.width(), self.height()))

    def _stretched_path(self, width: float, height: float) -> QPainterPath:
        """Barra estirada hacia adentro, unida al borde por un cuello que se afina al tirar."""
        edge = self.config.edge
        progress = min(1.0, self._pull / (DETACH_DISTANCE * PULL_GAIN))
        # Pie: un "charquito" pegado al borde que se achica a medida que la gota se estira.
        foot_len = max(24.0, self.bar_len * 0.75 * (1.0 - progress))
        if edge == "right":
            body = QRectF(0, 0, BAR, height)
            foot = QRectF(width - 8, (height - foot_len) / 2, 8, foot_len)
        elif edge == "left":
            body = QRectF(width - BAR, 0, BAR, height)
            foot = QRectF(0, (height - foot_len) / 2, 8, foot_len)
        else:
            body = QRectF(0, height - BAR, width, BAR)
            foot = QRectF((width - foot_len) / 2, 0, foot_len, 8)
        thickness = max(10.0, self.bar_len * 0.5 * (1.0 - progress))
        path = QPainterPath()
        path.addRoundedRect(body, BAR / 2, BAR / 2)
        foot_path = QPainterPath()
        foot_path.addRoundedRect(foot, 4, 4)
        return path.united(foot_path).united(bridge_path(foot, body, horizontal=is_vertical(edge),
                                                         thickness=thickness))

    def apply_config(self, config: DockConfig) -> None:
        """Aplica cambios de Configuración en vivo (borde, ancho, fijado, efecto líquido)."""
        self.config = config
        self.pin_button.setChecked(config.pinned)
        if not config.liquid:
            self.wobble_anim.stop()
            self.wobble, self._phase = 0.0, 0.0
        self._arrange()
        self.animation.stop()
        self._set_rect(self._target(self.revealed))

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
        self._refresh_shape()

    def resizeEvent(self, event) -> None:
        super().resizeEvent(event)
        self._update_shape()

    def reposition(self, *_args) -> None:
        self.animation.stop()
        self._set_rect(self._target(self.revealed))

    def _settle(self) -> None:
        """Vuelve la barra a su lugar en el borde con un pequeño rebote."""
        target = QRect(*self._target(False))
        self.animation.stop()
        if self.animation_ms <= 0 or not self.isVisible():
            self._set_rect(self._target(False))
            return
        self.animation.setDuration(self.animation_ms)
        self.animation.setStartValue(self.geometry())
        self.animation.setEndValue(target)
        self.animation.start()
        self.jiggle(0.8)

    # --- arrastre: estirar, despegar y volver a pegarse -------------------------------------

    def begin_drag(self, global_pos: QPoint) -> None:
        if self.revealed:
            return
        self.animation.stop()
        self._press_global = QPoint(global_pos)
        self._press_offset = global_pos - self.pos()
        self._drag_position = self.config.position
        self.dragging = False
        self.detached = False
        self._pull = 0.0

    def drag_to(self, global_pos: QPoint) -> None:
        if self._press_global is None:
            return
        delta = global_pos - self._press_global
        if not self.dragging and delta.manhattanLength() > DRAG_THRESHOLD:
            self.dragging = True
        if not self.dragging:
            return
        if self.detached:
            self.move(global_pos - self._press_offset)
            return
        edge = self.config.edge
        inward = {"right": -delta.x(), "left": delta.x(), "top": delta.y()}[edge]
        if inward > DETACH_DISTANCE:
            self._detach(global_pos)
            return
        along = delta.y() if is_vertical(edge) else delta.x()
        self._drag_position = self._position_after(along)
        self._pull = max(0.0, inward) * PULL_GAIN
        rect = stretched_rect(self._area(), edge, self._drag_position, self.bar_len, self._pull)
        self.setGeometry(QRect(*rect))
        self._refresh_shape()

    def _position_after(self, along: int) -> float:
        ax, ay, aw, ah = self._area()
        start_x, start_y, _, _ = bar_rect(self._area(), self.config.edge, self.config.position, self.bar_len)
        if is_vertical(self.config.edge):
            travel = max(1, ah - 2 * MARGIN - self.bar_len)
            value = (start_y + along - ay - MARGIN) / travel
        else:
            travel = max(1, aw - 2 * MARGIN - self.bar_len)
            value = (start_x + along - ax - MARGIN) / travel
        return round(max(0.0, min(1.0, value)), 4)

    def _detach(self, global_pos: QPoint) -> None:
        """La gota se corta del borde y sigue al mouse como una cápsula suelta."""
        self.detached = True
        self._pull = 0.0
        _, _, width, height = bar_rect(self._area(), self.config.edge, self._drag_position, self.bar_len)
        self._press_offset = QPoint(width // 2, height // 2)
        self.setGeometry(QRect(global_pos - self._press_offset, QSize(width, height)))
        self._refresh_shape()
        self.jiggle(1.0)

    def end_drag(self, global_pos: QPoint) -> None:
        if self._press_global is None:
            return
        self.drag_to(global_pos)
        was_dragging = self.dragging
        self._press_global = None
        self.dragging = False
        if not was_dragging:
            return
        if self.detached:
            self.detached = False
            edge, position = snap(self._area(), self.x(), self.y(), self.width(), self.height())
            self._save(edge=edge, position=position)
            self._arrange()
        else:
            self._pull = 0.0
            if self._drag_position != self.config.position:
                self._save(position=self._drag_position)
        self._settle()

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


def primary_area() -> Rect:
    geometry = QGuiApplication.primaryScreen().availableGeometry()
    return geometry.x(), geometry.y(), geometry.width(), geometry.height()
