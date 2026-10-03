"""Ventana de Configuración: Planes de IA, Red (IP) y Apariencia."""

from __future__ import annotations

from dataclasses import replace
from typing import Callable

from PySide6.QtCore import QSize, Qt
from PySide6.QtWidgets import (
    QAbstractItemView,
    QCheckBox,
    QComboBox,
    QFormLayout,
    QHBoxLayout,
    QHeaderView,
    QLabel,
    QListWidget,
    QListWidgetItem,
    QPushButton,
    QSpinBox,
    QStackedWidget,
    QTableWidget,
    QTableWidgetItem,
    QVBoxLayout,
    QWidget,
)

from ipswitch.config import AppConfig, ConfigError, parse_config

from .config import DockConfig
from .icons import svg_icon
from .theme import themed
from .worker import RunAsync, run_async

COLUMNS = ("Nombre", "IP", "Prefijo", "Gateway", "DNS")
EDGE_LABELS = (("Derecha", "right"), ("Izquierda", "left"), ("Arriba", "top"))

STYLE = themed("""
QWidget { background: #161922; color: #e6edf3; font-family: 'Segoe UI'; font-size: 13px; }
QListWidget { background: #11131a; border: none; padding: 8px; outline: none; }
QListWidget::item { padding: 10px 12px; border-radius: @controlpx; margin: 2px 0; }
QListWidget::item:selected { background: #263247; color: #ffffff; }
QLabel#pageTitle { font-size: 18px; font-weight: 600; }
QLabel#hint { color: #8b949e; }
QLabel#message { color: #79c0ff; }
QPushButton { background: #232838; border: 1px solid #343b4f; border-radius: @controlpx; padding: 7px 14px; }
QPushButton:hover { background: #2c3347; }
QPushButton:disabled { color: #6e7681; }
QPushButton#primary { background: #2f6feb; border-color: #4c8dff; color: white; }
QPushButton#primary:hover { background: #3b7bf5; }
QComboBox, QSpinBox { background: #1d2130; border: 1px solid #343b4f; border-radius: @controlpx; padding: 5px 8px; }
QTableWidget { background: #1a1e2a; border: 1px solid #2b3245; border-radius: @cardpx; gridline-color: #2b3245; }
QHeaderView::section { background: #1f2433; color: #9da7b3; border: none; padding: 6px; }
QCheckBox { spacing: 8px; }
QCheckBox::indicator { width: 16px; height: 16px; border: 1px solid #4c566a; border-radius: @smallpx; background: #1d2130; }
QCheckBox::indicator:checked { background: #2f6feb; border-color: #4c8dff; }
""")


def _title(text: str, hint: str) -> list[QWidget]:
    title = QLabel(text)
    title.setObjectName("pageTitle")
    sub = QLabel(hint)
    sub.setObjectName("hint")
    sub.setWordWrap(True)
    return [title, sub]


def _button(text: str, icon: str | None = None, primary: bool = False) -> QPushButton:
    button = QPushButton(text)
    if primary:
        button.setObjectName("primary")
    svg = svg_icon(icon, size=15) if icon else None
    if svg is not None:
        button.setIcon(svg)
        button.setIconSize(QSize(15, 15))
    return button


class AppearancePage(QWidget):
    def __init__(self, window: "SettingsWindow"):
        super().__init__()
        self.window = window
        layout = QVBoxLayout(self)
        for widget in _title("Apariencia", "Dónde se pega la gota y cómo se comporta."):
            layout.addWidget(widget)
        form = QFormLayout()
        self.edge = QComboBox()
        for label, value in EDGE_LABELS:
            self.edge.addItem(label, value)
        self.edge.setCurrentIndex(self.edge.findData(window.config.edge))
        self.width = QSpinBox()
        self.width.setRange(280, 480)
        self.width.setSingleStep(10)
        self.width.setSuffix(" px")
        self.width.setValue(window.config.width)
        self.liquid = QCheckBox("Efecto líquido (ondas al abrir y al pasar el mouse)")
        self.liquid.setChecked(window.config.liquid)
        form.addRow("Borde de la pantalla", self.edge)
        form.addRow("Ancho de las apps", self.width)
        form.addRow("", self.liquid)
        layout.addLayout(form)
        layout.addStretch(1)
        self.save_button = _button("Guardar", primary=True)
        self.save_button.clicked.connect(self.save)
        layout.addWidget(self.save_button, 0, Qt.AlignmentFlag.AlignRight)

    def save(self) -> None:
        self.window.save_dock(edge=self.edge.currentData(), width=self.width.value(),
                              liquid=self.liquid.isChecked())


class AiPage(QWidget):
    def __init__(self, window: "SettingsWindow", installed: Callable[[], bool],
                 install: Callable[[], object], uninstall: Callable[[], object]):
        super().__init__()
        self.window = window
        self._installed, self._install, self._uninstall = installed, install, uninstall
        layout = QVBoxLayout(self)
        for widget in _title("Planes de IA", "Qué planes mostrar en la app Uso de IA (barras 0-100 %)."):
            layout.addWidget(widget)
        sources = window.config.ai_sources
        self.claude = QCheckBox("Claude (límites de 5 h y semanal)")
        self.claude.setChecked("claude" in sources)
        self.codex = QCheckBox("Codex (último dato guardado por Codex CLI)")
        self.codex.setChecked("codex" in sources)
        layout.addWidget(self.claude)
        layout.addWidget(self.codex)
        row = QHBoxLayout()
        self.statusline_label = QLabel("")
        self.statusline_label.setWordWrap(True)
        self.statusline_button = _button("")
        self.statusline_button.clicked.connect(self.toggle_statusline)
        row.addWidget(self.statusline_label, 1)
        row.addWidget(self.statusline_button)
        layout.addSpacing(10)
        layout.addLayout(row)
        self.message = QLabel("")
        self.message.setObjectName("message")
        self.message.setWordWrap(True)
        layout.addWidget(self.message)
        layout.addStretch(1)
        self.save_button = _button("Guardar", primary=True)
        self.save_button.clicked.connect(self.save)
        layout.addWidget(self.save_button, 0, Qt.AlignmentFlag.AlignRight)
        self._show_statusline()

    def _show_statusline(self) -> None:
        active = self._installed()
        self.statusline_label.setText(
            "Registrador de Claude: activo. Claude Code guarda tu uso en cada actualización de la status line."
            if active else
            "Registrador de Claude: inactivo. Activalo para leer el uso desde la status line oficial "
            "(tu status line actual se mantiene)."
        )
        self.statusline_button.setText("Desactivar" if active else "Activar")

    def toggle_statusline(self) -> None:
        try:
            (self._uninstall if self._installed() else self._install)()
        except (OSError, ValueError) as exc:
            self.message.setText(f"No se pudo cambiar la status line: {exc}")
        self._show_statusline()

    def save(self) -> None:
        sources = tuple(name for name, box in (("claude", self.claude), ("codex", self.codex)) if box.isChecked())
        self.window.save_dock(ai_sources=sources)
        self.message.setText("Guardado.")


class NetworkPage(QWidget):
    def __init__(self, window: "SettingsWindow", load: Callable[[], AppConfig],
                 adapters: Callable[[], list[str]], save: Callable[[AppConfig], None], run: RunAsync):
        super().__init__()
        self._load, self._adapters, self._save, self._run = load, adapters, save, run
        layout = QVBoxLayout(self)
        for widget in _title("Red (IP)", "Adaptador y perfiles de IP fija. Guardar pide permiso de administrador "
                                          "una vez, porque el archivo está protegido."):
            layout.addWidget(widget)
        form = QFormLayout()
        self.adapter = QComboBox()
        self.adapter.setEditable(True)
        form.addRow("Adaptador", self.adapter)
        layout.addLayout(form)
        self.table = QTableWidget(0, len(COLUMNS))
        self.table.setHorizontalHeaderLabels(COLUMNS)
        self.table.horizontalHeader().setSectionResizeMode(QHeaderView.ResizeMode.Stretch)
        self.table.verticalHeader().setVisible(False)
        self.table.setSelectionBehavior(QAbstractItemView.SelectionBehavior.SelectRows)
        layout.addWidget(self.table, 1)
        tools = QHBoxLayout()
        self.add_button = _button("Agregar", "plus")
        self.add_button.clicked.connect(lambda: self.add_row())
        self.remove_button = _button("Quitar", "trash-2")
        self.remove_button.clicked.connect(self.remove_selected)
        tools.addWidget(self.add_button)
        tools.addWidget(self.remove_button)
        tools.addStretch(1)
        self.save_button = _button("Guardar", primary=True)
        self.save_button.clicked.connect(self.save)
        tools.addWidget(self.save_button)
        layout.addLayout(tools)
        self.message = QLabel("")
        self.message.setObjectName("message")
        self.message.setWordWrap(True)
        layout.addWidget(self.message)
        self.reload()

    def reload(self) -> None:
        def fetch():
            config = self._load()
            try:
                adapters = self._adapters()
            except Exception:  # noqa: BLE001 - la lista de adaptadores es opcional
                adapters = []
            return config, adapters

        self.save_button.setEnabled(False)
        self._run(fetch, self._fill, self._load_failed)

    def _fill(self, value) -> None:
        config, adapters = value
        self.adapter.clear()
        for name in [config.adapter] + [a for a in adapters if a != config.adapter]:
            self.adapter.addItem(name)
        self.table.setRowCount(0)
        for profile in config.profiles:
            self.add_row([profile.name, profile.ip, str(profile.prefix), profile.gateway, ", ".join(profile.dns)])
        self.save_button.setEnabled(True)

    def _load_failed(self, exc: Exception) -> None:
        self.message.setText(str(exc))
        self.save_button.setEnabled(False)

    def add_row(self, values: list[str] | None = None) -> None:
        row = self.table.rowCount()
        self.table.insertRow(row)
        for column in range(len(COLUMNS)):
            text = values[column] if values else ""
            self.table.setItem(row, column, QTableWidgetItem(text))

    def remove_selected(self) -> None:
        for row in sorted({index.row() for index in self.table.selectedIndexes()}, reverse=True):
            self.table.removeRow(row)

    def collect(self) -> AppConfig:
        def cell(row: int, column: int) -> str:
            item = self.table.item(row, column)
            return item.text().strip() if item else ""

        profiles = []
        for row in range(self.table.rowCount()):
            values = [cell(row, column) for column in range(len(COLUMNS))]
            if not any(values):
                continue  # fila vacía (por ejemplo, recién agregada): se ignora
            name, ip, prefix, gateway, dns = values
            if not (name and ip and prefix and gateway):
                label = name or f"fila {row + 1}"
                raise ConfigError(f"Perfil {label}: completá nombre, IP, prefijo y gateway.")
            profiles.append({"name": name, "ip": ip, "prefix": prefix, "gateway": gateway,
                             "dns": [d.strip() for d in dns.split(",") if d.strip()]})
        return parse_config({"adapter": self.adapter.currentText().strip(), "profiles": profiles}, "perfiles")

    def save(self) -> None:
        try:
            config = self.collect()
        except ConfigError as exc:
            self.message.setText(str(exc))
            return
        self.save_button.setEnabled(False)
        self.message.setText("Pidiendo permiso de administrador…")
        self._run(lambda: self._save(config), self._saved, self._save_failed)

    def _saved(self, _value) -> None:
        self.save_button.setEnabled(True)
        self.message.setText("Guardado. Los botones del panel se actualizan en unos segundos.")

    def _save_failed(self, exc: Exception) -> None:
        self.save_button.setEnabled(True)
        self.message.setText(str(exc))


class SettingsWindow(QWidget):
    def __init__(
        self,
        config: DockConfig,
        on_dock_save: Callable[[DockConfig], None],
        ip_load: Callable[[], AppConfig],
        ip_adapters: Callable[[], list[str]],
        ip_save: Callable[[AppConfig], None],
        statusline_installed: Callable[[], bool],
        statusline_install: Callable[[], object],
        statusline_uninstall: Callable[[], object],
        run: RunAsync = run_async,
    ):
        super().__init__(None, Qt.WindowType.Window)
        self.setWindowTitle("IPDock · Configuración")
        self.setStyleSheet(STYLE)
        self.resize(820, 520)
        self.config = config
        self._on_dock_save = on_dock_save
        layout = QHBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(0)
        self.nav = QListWidget()
        self.nav.setFixedWidth(190)
        self.stack = QStackedWidget()
        self.ai = AiPage(self, statusline_installed, statusline_install, statusline_uninstall)
        self.network = NetworkPage(self, ip_load, ip_adapters, ip_save, run)
        self.appearance = AppearancePage(self)
        self._pages = {"Planes de IA": (self.ai, "bot"), "Red (IP)": (self.network, "network"),
                       "Apariencia": (self.appearance, "palette")}
        for name, (page, icon) in self._pages.items():
            item = QListWidgetItem(name)
            svg = svg_icon(icon, size=16)
            if svg is not None:
                item.setIcon(svg)
            self.nav.addItem(item)
            page.layout().setContentsMargins(24, 20, 24, 20)
            self.stack.addWidget(page)
        self.nav.currentRowChanged.connect(self.stack.setCurrentIndex)
        self.nav.setCurrentRow(0)
        layout.addWidget(self.nav)
        layout.addWidget(self.stack, 1)

    def section_names(self) -> list[str]:
        return list(self._pages)

    def show_section(self, name: str) -> None:
        self.nav.setCurrentRow(self.section_names().index(name))

    def save_dock(self, **changes) -> None:
        self.config = replace(self.config, **changes)
        self._on_dock_save(self.config)
