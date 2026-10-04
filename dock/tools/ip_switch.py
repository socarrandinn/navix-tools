from __future__ import annotations

from typing import Callable

from PySide6.QtCore import QSize, Qt, QTimer
from PySide6.QtWidgets import QGridLayout, QHBoxLayout, QLabel, QPushButton, QVBoxLayout, QWidget

from ipswitch.actions import active_label
from ipswitch.client import request_switch
from ipswitch.config import AppConfig, default_config_path, load_config
from ipswitch.helper import Result
from ipswitch.status import describe, read_status

from ..icons import svg_icon
from ..tool import Tool
from ..worker import RunAsync, run_async

GREEN = "#3fb950"
BLUE = "#58a6ff"
GREY = "#8b949e"
RED = "#f85149"


class OptionCard(QPushButton):
    """Opción de red como tarjeta: ícono, nombre e IP (o "Automática" para DHCP)."""

    def __init__(self, icon: str, title: str, detail: str):
        super().__init__()
        self.setObjectName("optionCard")
        self.setAccessibleName(title)
        self.setMinimumHeight(52)
        self.set_active(False)
        row = QHBoxLayout(self)
        row.setContentsMargins(10, 8, 10, 8)
        row.setSpacing(10)
        self.icon_label = QLabel()
        svg = svg_icon(icon, color="#c9d1d9", size=18)
        if svg is not None:
            self.icon_label.setPixmap(svg.pixmap(QSize(18, 18)))
        texts = QVBoxLayout()
        texts.setSpacing(0)
        self.title = QLabel(title)
        self.title.setObjectName("optionTitle")
        self.detail = QLabel(detail)
        self.detail.setObjectName("optionDetail")
        texts.addWidget(self.title)
        texts.addWidget(self.detail)
        row.addWidget(self.icon_label)
        row.addLayout(texts, 1)
        for label in (self.icon_label, self.title, self.detail):
            label.setAttribute(Qt.WidgetAttribute.WA_TransparentForMouseEvents)

    def set_active(self, active: bool) -> None:
        """La opción ya aplicada se resalta pero no se puede volver a elegir."""
        self.active = active
        self.setProperty("active", active)
        name = self.accessibleName()
        self.setToolTip(f"{name}: perfil activo" if active else f"Cambiar a {name}")
        self.setCursor(Qt.CursorShape.ArrowCursor if active else Qt.CursorShape.PointingHandCursor)
        self.style().unpolish(self)
        self.style().polish(self)

    def hitButton(self, pos) -> bool:
        return not self.active and super().hitButton(pos)


class IpSwitchTool(Tool):
    title = "Cambio de IP"
    icon = "network"
    refresh_ms = 10_000

    def __init__(
        self,
        load: Callable[[], AppConfig] | None = None,
        read=read_status,
        switch=request_switch,
        run: RunAsync = run_async,
        settle_ms: int = 3000,
    ):
        self._load = load or (lambda: load_config(default_config_path()))
        self._read = read
        self._switch = switch
        self._run = run
        self.settle_ms = settle_ms
        self.busy = False
        self.loading = False
        self.buttons: list[OptionCard] = []
        self._button_keys: list[tuple[str, str | None]] = []
        self._button_names: tuple[str, ...] | None = None

    def create_widget(self) -> QWidget:
        widget = QWidget()
        self.widget = widget
        layout = QVBoxLayout(widget)
        layout.setContentsMargins(0, 0, 0, 0)
        row = QHBoxLayout()
        self.dot = QLabel("●")
        self.label = QLabel("…")
        self.label.setStyleSheet("font-size: 15px; font-weight: 600;")
        row.addWidget(self.dot)
        row.addWidget(self.label)
        row.addStretch(1)
        layout.addLayout(row)
        self.grid = QGridLayout()
        layout.addLayout(self.grid)
        self.message = QLabel("")
        self.message.setWordWrap(True)
        layout.addWidget(self.message)
        self._set_dot(GREY)
        return widget

    def refresh(self) -> None:
        if self.busy or self.loading:
            return
        self.loading = True
        self._run(self._fetch, self._show, self._show_error)

    def _fetch(self):
        config = self._load()
        return config, self._read(config.adapter)

    def _show(self, value) -> None:
        self.loading = False
        config, status = value
        self.label.setText(active_label(status, config.profiles))
        self.label.setToolTip(describe(status))
        self._set_dot(BLUE if status.dhcp else GREEN)
        self._build_buttons(tuple(config.profiles))
        active = ("dhcp", None) if status.dhcp else next(
            (("profile", p.name) for p in config.profiles if p.ip == status.ip and p.prefix == status.prefix),
            None,
        )
        self._mark_active(active)

    def _show_error(self, exc: Exception) -> None:
        self.loading = False
        self.label.setText("Sin estado")
        self.label.setToolTip("")
        self._set_dot(GREY)
        self._set_message(str(exc), RED)

    def _build_buttons(self, profiles: tuple) -> None:
        if profiles == self._button_names:
            return
        for button in self.buttons:
            self.grid.removeWidget(button)
            button.deleteLater()
        self.buttons = []
        self._button_keys = []
        self._button_names = profiles
        options = [("wifi", "DHCP", "Automática", "dhcp", None)] + [
            ("network", p.name, f"{p.ip}/{p.prefix}", "profile", p.name) for p in profiles
        ]
        for index, (icon, title, detail, action, profile) in enumerate(options):
            button = OptionCard(icon, title, detail)
            button.clicked.connect(lambda _checked=False, a=action, p=profile: self.switch(a, p))
            self.grid.addWidget(button, index, 0)  # una tarjeta por fila: la IP entra completa
            self.buttons.append(button)
            self._button_keys.append((action, profile))

    def _mark_active(self, active: tuple[str, str | None] | None) -> None:
        for button, key in zip(self.buttons, self._button_keys):
            button.set_active(key == active)

    def switch(self, action: str, profile: str | None = None) -> None:
        if self.busy:
            return
        self.busy = True
        self._enable(False)
        self._set_message("Aplicando…", GREY)
        self._run(lambda: self._switch(action, profile), self._switched, self._switch_failed)

    def _switched(self, result: Result) -> None:
        self.busy = False
        self._enable(True)
        self._set_message(result.message, GREY if result.ok else RED)
        self.refresh()
        # DHCP tarda unos segundos en obtener lease: segundo refresco cuando se asienta.
        QTimer.singleShot(self.settle_ms, self.widget, self.refresh)

    def _switch_failed(self, exc: Exception) -> None:
        self.busy = False
        self._enable(True)
        self._set_message(str(exc), RED)

    def _enable(self, enabled: bool) -> None:
        for button in self.buttons:
            button.setEnabled(enabled)

    def _set_dot(self, color: str) -> None:
        self.dot.setStyleSheet(f"color: {color}; font-size: 16px;")

    def _set_message(self, text: str, color: str) -> None:
        self.message.setText(text)
        self.message.setStyleSheet(f"color: {color};")


def create_tool() -> Tool:
    return IpSwitchTool()
