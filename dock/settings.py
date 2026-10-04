"""Ventana de Configuración: General, Planes de IA, Red (IP), Notificaciones y Apariencia."""

from __future__ import annotations

import ctypes
from dataclasses import replace
from datetime import datetime, timezone
from pathlib import Path
from typing import Callable, Sequence

from PySide6.QtCore import QRectF, QSize, Qt
from PySide6.QtGui import QColor, QIcon, QPainter
from PySide6.QtWidgets import (
    QCheckBox,
    QComboBox,
    QDialog,
    QFileDialog,
    QFrame,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QListWidget,
    QListWidgetItem,
    QPushButton,
    QScrollArea,
    QSpinBox,
    QStackedWidget,
    QVBoxLayout,
    QWidget,
)

from ipswitch.config import AppConfig, ConfigError, parse_config
from ipswitch.models import ProfileError, StaticProfile

from .brand import APP_NAME
from .config import DockConfig
from .icons import ICON_DIR, svg_icon
from .theme import themed
from .usage import UsageSnapshot, age_text
from .worker import RunAsync, run_async

EDGE_LABELS = (("Derecha", "right"), ("Izquierda", "left"), ("Arriba", "top"))
TOOL_ICONS = {"ip_switch": "network", "ai_usage": "gauge"}
ACCENT = "#4c8dff"

STYLE = themed("""
QWidget { background: #141720; color: #e6edf3; font-family: 'Segoe UI'; font-size: 13px; }
QWidget#sidebar { background: #10131a; }
QLabel#sidebarTitle { font-size: 16px; font-weight: 600; background: transparent; }
QListWidget { background: transparent; border: none; outline: none; }
QListWidget::item { padding: 9px 12px; border-radius: @controlpx; margin: 1px 0; color: #c9d1d9; }
QListWidget::item:hover { background: rgba(255, 255, 255, 14); }
QListWidget::item:selected { background: rgba(76, 141, 255, 38); color: #ffffff; }
QLabel#pageTitle { font-size: 19px; font-weight: 600; background: transparent; }
QLabel#hint, QLabel#rowHint { color: #8b949e; background: transparent; }
QLabel#rowHint { font-size: 12px; }
QLabel#badge { background: rgba(76, 141, 255, 40); border-radius: 18px; }
QLabel#message { color: #79c0ff; background: transparent; }
QFrame#group QLabel#pillOn, QLabel#pillOn { background: rgba(63, 185, 80, 40); color: #56d364; border-radius: @smallpx; padding: 2px 10px; }
QFrame#group QLabel#pillOff, QLabel#pillOff { background: rgba(139, 148, 158, 40); color: #c9d1d9; border-radius: @smallpx; padding: 2px 10px; }
QFrame#group { background: #1a1e29; border: 1px solid rgba(255, 255, 255, 18); border-radius: @cardpx; }
QFrame#group QWidget { background: transparent; }
QFrame#divider { background: rgba(255, 255, 255, 16); max-height: 1px; border: none; }
QPushButton { background: #232838; border: 1px solid #343b4f; border-radius: @controlpx; padding: 7px 14px; }
QPushButton:hover { background: #2c3347; }
QPushButton:disabled { color: #6e7681; }
QPushButton#primary { background: #2f6feb; border-color: #4c8dff; color: white; padding: 8px 18px; }
QPushButton#primary:hover { background: #3b7bf5; }
QComboBox, QSpinBox, QLineEdit { background: #12151d; border: 1px solid #343b4f; border-radius: @controlpx;
                                 padding: 6px 10px; selection-background-color: #2f6feb; }
QComboBox:hover, QSpinBox:hover, QLineEdit:hover { border-color: #4a5470; }
QComboBox:focus, QSpinBox:focus, QLineEdit:focus { border-color: #4c8dff; }
QComboBox::drop-down { border: none; width: 28px; }
QComboBox::down-arrow { image: url(@chevron); width: 14px; height: 14px; }
QComboBox QAbstractItemView { background: #1a1e29; border: 1px solid #343b4f; border-radius: @controlpx;
                              padding: 4px; outline: none; selection-background-color: rgba(76, 141, 255, 60); }
QComboBox QAbstractItemView::item { min-height: 30px; padding: 4px 8px; border-radius: @smallpx; }
QComboBox QAbstractItemView::item:hover { background: rgba(255, 255, 255, 18); }
QFrame#profileCard { background: #1a1e29; border: 1px solid rgba(255, 255, 255, 18); border-radius: @cardpx; }
QFrame#profileCard:hover { border-color: rgba(76, 141, 255, 120); }
QFrame#profileCard QWidget, QFrame#profileCard QLabel { background: transparent; }
QFrame#profileCard QLabel#badge { background: rgba(76, 141, 255, 40); border-radius: 17px; }
QLabel#cardName { font-weight: 600; }
QLabel#sectionTitle { font-size: 14px; font-weight: 600; background: transparent; }
QLabel#error { color: #ff7b72; background: transparent; }
QPushButton#ghost { background: transparent; border: none; border-radius: 16px; padding: 0px; }
QPushButton#ghost:hover { background: rgba(255, 255, 255, 30); }
QScrollArea { background: transparent; border: none; }
QScrollArea > QWidget > QWidget { background: transparent; }
QCheckBox { spacing: 10px; background: transparent; }
QCheckBox::indicator { width: 36px; height: 20px; border-radius: @smallpx; background: #2b3245; border: 1px solid #3a4258; }
QCheckBox::indicator:checked { background: #2f6feb; border-color: #4c8dff; }
""").replace("@chevron", (ICON_DIR / "chevron-down-light.svg").as_posix())


DWMWA_USE_IMMERSIVE_DARK_MODE = 20


def dark_title_bar(hwnd: int) -> bool:
    """Pide a Windows la barra de título oscura (Windows 10 20H1+ / 11). False si no se pudo."""
    if not hwnd:
        return False
    try:
        value = ctypes.c_int(1)
        result = ctypes.windll.dwmapi.DwmSetWindowAttribute(
            ctypes.c_void_p(hwnd), DWMWA_USE_IMMERSIVE_DARK_MODE, ctypes.byref(value), ctypes.sizeof(value))
    except (AttributeError, OSError):
        return False
    return result == 0


# --- piezas de UI reutilizables -----------------------------------------------------------

def _icon_label(name: str, size: int = 18, color: str = "#c9d1d9") -> QLabel:
    label = QLabel()
    icon = svg_icon(name, color=color, size=size)
    if icon is not None:
        label.setPixmap(icon.pixmap(QSize(size, size)))
    label.setFixedSize(size + 4, size + 4)
    label.setAlignment(Qt.AlignmentFlag.AlignCenter)
    return label


def _header(icon: str, title: str, hint: str) -> QWidget:
    widget = QWidget()
    row = QHBoxLayout(widget)
    row.setContentsMargins(0, 0, 0, 8)
    row.setSpacing(14)
    badge = QLabel()
    badge.setObjectName("badge")
    badge.setFixedSize(36, 36)
    badge.setAlignment(Qt.AlignmentFlag.AlignCenter)
    svg = svg_icon(icon, color=ACCENT, size=18)
    if svg is not None:
        badge.setPixmap(svg.pixmap(QSize(18, 18)))
    texts = QVBoxLayout()
    texts.setSpacing(2)
    title_label = QLabel(title)
    title_label.setObjectName("pageTitle")
    hint_label = QLabel(hint)
    hint_label.setObjectName("hint")
    hint_label.setWordWrap(True)
    texts.addWidget(title_label)
    texts.addWidget(hint_label)
    row.addWidget(badge, 0, Qt.AlignmentFlag.AlignTop)
    row.addLayout(texts, 1)
    return widget


def _group() -> tuple[QFrame, QVBoxLayout]:
    frame = QFrame()
    frame.setObjectName("group")
    layout = QVBoxLayout(frame)
    layout.setContentsMargins(16, 6, 16, 6)
    layout.setSpacing(0)
    return frame, layout


def _row(group: QVBoxLayout, icon: str, title: str, hint: str, control: QWidget | None) -> None:
    """Fila de opción: ícono, título (y ayuda) a la izquierda, control a la derecha."""
    if group.count():
        divider = QFrame()
        divider.setObjectName("divider")
        group.addWidget(divider)
    widget = QWidget()
    row = QHBoxLayout(widget)
    row.setContentsMargins(0, 10, 0, 10)
    row.setSpacing(12)
    row.addWidget(_icon_label(icon))
    texts = QVBoxLayout()
    texts.setSpacing(1)
    texts.addWidget(QLabel(title))
    if hint:
        hint_label = QLabel(hint)
        hint_label.setObjectName("rowHint")
        hint_label.setWordWrap(True)
        texts.addWidget(hint_label)
    row.addLayout(texts, 1)
    if control is not None:
        row.addWidget(control, 0, Qt.AlignmentFlag.AlignVCenter)
    group.addWidget(widget)


def _button(text: str, icon: str | None = None, primary: bool = False) -> QPushButton:
    button = QPushButton(text)
    if primary:
        button.setObjectName("primary")
    svg = svg_icon(icon, color="#ffffff" if primary else "#c9d1d9", size=15) if icon else None
    if svg is not None:
        button.setIcon(svg)
        button.setIconSize(QSize(15, 15))
    return button


class Switch(QCheckBox):
    """Interruptor dibujado: riel redondeado y perilla que se desliza."""

    def sizeHint(self) -> QSize:
        return QSize(40, 22)

    def hitButton(self, pos) -> bool:
        return self.rect().contains(pos)

    def paintEvent(self, event) -> None:
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)
        painter.setPen(Qt.PenStyle.NoPen)
        track = QRectF(1, 1, self.width() - 2, self.height() - 2)
        painter.setBrush(QColor("#2f6feb") if self.isChecked() else QColor("#2b3245"))
        painter.drawRoundedRect(track, track.height() / 2, track.height() / 2)
        knob = track.height() - 6
        x = track.right() - knob - 3 if self.isChecked() else track.left() + 3
        painter.setBrush(QColor("#ffffff") if self.isEnabled() else QColor("#8b949e"))
        painter.drawEllipse(QRectF(x, track.top() + 3, knob, knob))


def _switch(checked: bool, name: str = "") -> QCheckBox:
    box = Switch()
    box.setFixedSize(40, 22)
    box.setChecked(checked)
    box.setAccessibleName(name)
    return box


def _message() -> QLabel:
    label = QLabel("")
    label.setObjectName("message")
    label.setWordWrap(True)
    return label


def _footer(layout: QVBoxLayout, message: QLabel, *buttons: QPushButton) -> None:
    row = QHBoxLayout()
    row.addWidget(message, 1)
    for button in buttons:
        row.addWidget(button)
    layout.addLayout(row)


class _Page(QWidget):
    def __init__(self, icon: str, title: str, hint: str):
        super().__init__()
        self.page_layout = QVBoxLayout(self)
        self.page_layout.setSpacing(14)
        self.page_layout.addWidget(_header(icon, title, hint))


# --- páginas ------------------------------------------------------------------------------

class GeneralPage(_Page):
    def __init__(self, window: "SettingsWindow", available: Sequence[tuple[str, str]]):
        super().__init__("settings", "General", "Qué apps aparecen en la barra.")
        self.window = window
        frame, group = _group()
        self.tool_boxes: dict[str, QCheckBox] = {}
        for name, title in available:
            box = _switch(name in window.config.tools, title)
            self.tool_boxes[name] = box
            _row(group, TOOL_ICONS.get(name, "settings"), title, "", box)
        self.page_layout.addWidget(frame)
        self.page_layout.addStretch(1)
        self.message = _message()
        self.save_button = _button("Guardar", primary=True)
        self.save_button.clicked.connect(self.save)
        _footer(self.page_layout, self.message, self.save_button)

    def save(self) -> None:
        tools = tuple(name for name, box in self.tool_boxes.items() if box.isChecked())
        if not tools:
            self.message.setText("Elegí al menos una app.")
            return
        self.window.save_dock(tools=tools)
        self.message.setText("Guardado.")


UsageProbe = Callable[[str, DockConfig], "UsageSnapshot | None"]
DEFAULT_CODEX_FOLDER = Path.home() / ".codex" / "sessions"


class AiPage(_Page):
    def __init__(self, window: "SettingsWindow", installed: Callable[[], bool],
                 install: Callable[[], object], uninstall: Callable[[], object],
                 probe: UsageProbe, run: RunAsync):
        super().__init__("bot", "Planes de IA", "Qué planes mostrar en Uso de IA y de dónde se leen.")
        self.window = window
        self._installed, self._install, self._uninstall = installed, install, uninstall
        self._probe, self._run = probe, run
        sources = window.config.ai_sources
        frame, group = _group()
        self.claude = _switch("claude" in sources, "Claude")
        self.codex = _switch("codex" in sources, "Codex")
        _row(group, "bot", "Claude", "Límites de 5 h y semanal, desde la status line oficial.", self.claude)
        _row(group, "gauge", "Codex", "Último dato guardado por Codex CLI.", self.codex)
        self.page_layout.addWidget(frame)

        recorder, recorder_group = _group()
        status = QWidget()
        status_row = QHBoxLayout(status)
        status_row.setContentsMargins(0, 0, 0, 0)
        status_row.setSpacing(8)
        self.statusline_pill = QLabel("")
        self.statusline_button = _button("")
        self.statusline_button.clicked.connect(self.toggle_statusline)
        status_row.addWidget(self.statusline_pill)
        status_row.addWidget(self.statusline_button)
        _row(recorder_group, "settings", "Registrador de Claude",
             "Guarda tu uso en cada actualización de la status line; tu status line actual se mantiene.", status)
        self.page_layout.addWidget(recorder)

        # Conexiones: si cada fuente local tiene datos y de cuándo son.
        connections, connections_group = _group()
        self.connection_pills: dict[str, QLabel] = {}
        self.connection_details: dict[str, QLabel] = {}
        self.test_buttons: dict[str, QPushButton] = {}
        for source, icon, title in (("claude", "bot", "Conexión con Claude"), ("codex", "gauge", "Conexión con Codex")):
            cell = QWidget()
            cell_row = QHBoxLayout(cell)
            cell_row.setContentsMargins(0, 0, 0, 0)
            cell_row.setSpacing(8)
            pill, detail, test = QLabel("…"), QLabel(""), _button("Probar")
            pill.setObjectName("pillOff")
            detail.setObjectName("rowHint")
            test.clicked.connect(lambda _checked=False, s=source: self.test_connection(s))
            cell_row.addWidget(detail)
            cell_row.addWidget(pill)
            cell_row.addWidget(test)
            self.connection_pills[source], self.connection_details[source] = pill, detail
            self.test_buttons[source] = test
            _row(connections_group, icon, title, "Lee los datos locales; no usa claves ni APIs.", cell)
        folder = QWidget()
        folder_row = QHBoxLayout(folder)
        folder_row.setContentsMargins(0, 0, 0, 0)
        folder_row.setSpacing(8)
        self.codex_folder = QLineEdit(window.config.codex_sessions)
        self.codex_folder.setPlaceholderText(str(DEFAULT_CODEX_FOLDER))
        self.codex_folder.setMinimumWidth(240)
        browse = _button("Elegir…")
        browse.clicked.connect(self.choose_codex_folder)
        folder_row.addWidget(self.codex_folder, 1)
        folder_row.addWidget(browse)
        _row(connections_group, "gauge", "Sesiones de Codex", "Vacío = carpeta por defecto de Codex CLI.", folder)
        self.page_layout.addWidget(connections)

        self.page_layout.addStretch(1)
        self.message = _message()
        self.save_button = _button("Guardar", primary=True)
        self.save_button.clicked.connect(self.save)
        _footer(self.page_layout, self.message, self.save_button)
        self._show_statusline()
        for source in self.connection_pills:
            self.test_connection(source)

    def test_connection(self, source: str) -> None:
        config = self.window.config
        self.connection_pills[source].setText("Probando…")
        self._run(lambda: self._probe(source, config),
                  lambda snapshot, s=source: self._show_connection(s, snapshot),
                  lambda exc, s=source: self._show_connection(s, None, str(exc)))

    def _show_connection(self, source: str, snapshot: UsageSnapshot | None, error: str = "") -> None:
        pill, detail = self.connection_pills[source], self.connection_details[source]
        ok = snapshot is not None
        pill.setText("Conectado" if ok else "Sin datos")
        pill.setObjectName("pillOn" if ok else "pillOff")
        pill.style().unpolish(pill)
        pill.style().polish(pill)
        detail.setText(error or (age_text(snapshot.captured_at, datetime.now(timezone.utc)) if ok else ""))

    def choose_codex_folder(self) -> None:
        start = self.codex_folder.text().strip() or str(DEFAULT_CODEX_FOLDER)
        folder = QFileDialog.getExistingDirectory(self, "Carpeta de sesiones de Codex", start)
        if folder:
            self.codex_folder.setText(folder)

    def _show_statusline(self) -> None:
        active = self._installed()
        self.statusline_pill.setText("Activo" if active else "Inactivo")
        self.statusline_pill.setObjectName("pillOn" if active else "pillOff")
        self.statusline_pill.style().unpolish(self.statusline_pill)
        self.statusline_pill.style().polish(self.statusline_pill)
        self.statusline_button.setText("Desactivar" if active else "Activar")

    def toggle_statusline(self) -> None:
        try:
            (self._uninstall if self._installed() else self._install)()
        except (OSError, ValueError) as exc:
            self.message.setText(f"No se pudo cambiar la status line: {exc}")
        self._show_statusline()

    def save(self) -> None:
        sources = tuple(name for name, box in (("claude", self.claude), ("codex", self.codex)) if box.isChecked())
        folder = self.codex_folder.text().strip()
        if folder and not Path(folder).expanduser().is_dir():
            self.message.setText(f"La carpeta {folder} no existe.")
            return
        self.window.save_dock(ai_sources=sources, codex_sessions=folder)
        self.message.setText("Guardado.")
        self.test_connection("codex")


class ProfileEditor(QDialog):
    """Ventana para crear o editar un perfil de IP fija; valida antes de aceptar."""

    def __init__(self, profile: StaticProfile | None, parent: QWidget | None = None):
        super().__init__(parent)
        self.setWindowTitle("Editar perfil" if profile else "Nuevo perfil")
        self.setStyleSheet(STYLE)
        self.setMinimumWidth(420)
        layout = QVBoxLayout(self)
        layout.setContentsMargins(22, 20, 22, 18)
        layout.setSpacing(14)
        layout.addWidget(_header("network", "Editar perfil" if profile else "Nuevo perfil",
                                 "IP fija que se aplica al adaptador elegido."))
        frame, group = _group()
        self.name = QLineEdit(profile.name if profile else "")
        self.name.setPlaceholderText("Casa, Oficina…")
        self.ip = QLineEdit(profile.ip if profile else "")
        self.ip.setPlaceholderText("192.168.0.100")
        self.prefix = QSpinBox()
        self.prefix.setRange(1, 30)
        self.prefix.setPrefix("/")
        self.prefix.setValue(profile.prefix if profile else 24)
        self.gateway = QLineEdit(profile.gateway if profile else "")
        self.gateway.setPlaceholderText("192.168.0.1")
        dns = list(profile.dns) if profile else []
        self.dns1 = QLineEdit(dns[0] if dns else "")
        self.dns1.setPlaceholderText("8.8.8.8")
        self.dns2 = QLineEdit(dns[1] if len(dns) > 1 else "")
        self.dns2.setPlaceholderText("opcional")
        for field in (self.name, self.ip, self.gateway, self.dns1, self.dns2):
            field.setMinimumWidth(200)
        _row(group, "pencil", "Nombre", "", self.name)
        _row(group, "network", "Dirección IP", "", self.ip)
        _row(group, "network", "Prefijo", "24 = máscara 255.255.255.0", self.prefix)
        _row(group, "network", "Puerta de enlace", "", self.gateway)
        _row(group, "network", "DNS primario", "", self.dns1)
        _row(group, "network", "DNS secundario", "", self.dns2)
        layout.addWidget(frame)
        self.error = QLabel("")
        self.error.setObjectName("error")
        self.error.setWordWrap(True)
        cancel = _button("Cancelar")
        cancel.clicked.connect(self.reject)
        accept = _button("Aceptar", primary=True)
        accept.clicked.connect(self.try_accept)
        _footer(layout, self.error, cancel, accept)

    def profile(self) -> StaticProfile:
        dns = tuple(d for d in (self.dns1.text().strip(), self.dns2.text().strip()) if d)
        return StaticProfile(self.name.text().strip(), self.ip.text().strip(), self.prefix.value(),
                             self.gateway.text().strip(), dns)

    def try_accept(self) -> bool:
        try:
            self.profile().validate()
        except ProfileError as exc:
            self.error.setText(str(exc))
            return False
        self.accept()
        return True

    showEvent = None  # se reemplaza abajo para la barra de título oscura


def _editor_showevent(self, event) -> None:
    QDialog.showEvent(self, event)
    dark_title_bar(int(self.winId()))


ProfileEditor.showEvent = _editor_showevent


def edit_profile(profile: StaticProfile | None, parent: QWidget | None) -> StaticProfile | None:
    editor = ProfileEditor(profile, parent)
    return editor.profile() if editor.exec() == QDialog.DialogCode.Accepted else None


class ProfileCard(QFrame):
    """Tarjeta de un perfil: ícono, nombre, IP/prefijo, gateway y DNS, con editar y borrar."""

    def __init__(self, profile: StaticProfile):
        super().__init__()
        self.setObjectName("profileCard")
        self.profile = profile
        row = QHBoxLayout(self)
        row.setContentsMargins(14, 12, 10, 12)
        row.setSpacing(12)
        badge = QLabel()
        badge.setObjectName("badge")
        badge.setFixedSize(34, 34)
        badge.setAlignment(Qt.AlignmentFlag.AlignCenter)
        svg = svg_icon("network", color=ACCENT, size=16)
        if svg is not None:
            badge.setPixmap(svg.pixmap(QSize(16, 16)))
        row.addWidget(badge)
        texts = QVBoxLayout()
        texts.setSpacing(2)
        name = QLabel(profile.name)
        name.setObjectName("cardName")
        detail = QLabel(self._detail())
        detail.setObjectName("rowHint")
        texts.addWidget(name)
        texts.addWidget(detail)
        row.addLayout(texts, 1)
        self.edit_button = self._ghost("pencil", "Editar")
        self.remove_button = self._ghost("trash-2", "Quitar")
        row.addWidget(self.edit_button)
        row.addWidget(self.remove_button)

    def _detail(self) -> str:
        dns = ", ".join(self.profile.dns) if self.profile.dns else "sin DNS"
        return f"{self.profile.ip}/{self.profile.prefix} · gateway {self.profile.gateway} · DNS {dns}"

    def summary(self) -> str:
        return f"{self.profile.name} {self._detail()}"

    @staticmethod
    def _ghost(icon: str, tooltip: str) -> QPushButton:
        button = QPushButton("")
        button.setObjectName("ghost")
        button.setToolTip(tooltip)
        button.setFixedSize(32, 32)
        svg = svg_icon(icon, color="#c9d1d9", size=15)
        if svg is not None:
            button.setIcon(svg)
            button.setIconSize(QSize(15, 15))
        return button


class NetworkPage(_Page):
    def __init__(self, window: "SettingsWindow", load: Callable[[], AppConfig],
                 adapters: Callable[[], list[str]], save: Callable[[AppConfig], None], run: RunAsync):
        super().__init__("network", "Red (IP)", "Adaptador y perfiles de IP fija. Guardar pide permiso de "
                                                "administrador una vez, porque el archivo está protegido.")
        self._load, self._adapters, self._save, self._run = load, adapters, save, run
        self.editor: Callable[[StaticProfile | None, QWidget], StaticProfile | None] = edit_profile
        self.profiles: list[StaticProfile] = []
        self.cards: list[ProfileCard] = []
        frame, group = _group()
        self.adapter = QComboBox()
        self.adapter.setEditable(False)
        self.adapter.setMinimumWidth(240)
        self.adapter.view().setObjectName("adapterList")
        _row(group, "network", "Adaptador", "Interfaz de red que se configura.", self.adapter)
        self.page_layout.addWidget(frame)

        title_row = QHBoxLayout()
        title = QLabel("Perfiles de IP fija")
        title.setObjectName("sectionTitle")
        self.add_button = _button("Agregar perfil", "plus")
        self.add_button.clicked.connect(lambda: self._edit(None))
        title_row.addWidget(title, 1)
        title_row.addWidget(self.add_button)
        self.page_layout.addLayout(title_row)

        self.cards_box = QVBoxLayout()
        self.cards_box.setSpacing(8)
        holder = QWidget()
        holder.setLayout(self.cards_box)
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setFrameShape(QFrame.Shape.NoFrame)
        scroll.setWidget(holder)
        self.page_layout.addWidget(scroll, 1)

        self.message = _message()
        self.save_button = _button("Guardar", "check", primary=True)
        self.save_button.clicked.connect(self.save)
        _footer(self.page_layout, self.message, self.save_button)
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
            self.adapter.addItem(svg_icon("network", size=15) or QIcon(), name)
        self.profiles = list(config.profiles)
        self._render()
        self.save_button.setEnabled(True)

    def _load_failed(self, exc: Exception) -> None:
        self.message.setText(str(exc))
        self.save_button.setEnabled(False)

    def _render(self) -> None:
        for card in self.cards:
            self.cards_box.removeWidget(card)
            card.deleteLater()
        self.cards = []
        while self.cards_box.count():
            self.cards_box.takeAt(0)
        for index, profile in enumerate(self.profiles):
            card = ProfileCard(profile)
            card.edit_button.clicked.connect(lambda _=False, i=index: self._edit(i))
            card.remove_button.clicked.connect(lambda _=False, i=index: self._remove(i))
            self.cards_box.addWidget(card)
            self.cards.append(card)
        if not self.profiles:
            empty = QLabel("Sin perfiles. Agregá uno para poder cambiar a IP fija.")
            empty.setObjectName("hint")
            self.cards_box.addWidget(empty)
        self.cards_box.addStretch(1)

    def _edit(self, index: int | None) -> None:
        current = self.profiles[index] if index is not None else None
        result = self.editor(current, self)
        if result is None:
            return
        if index is None:
            self.profiles.append(result)
        else:
            self.profiles[index] = result
        self._render()

    def _remove(self, index: int) -> None:
        del self.profiles[index]
        self._render()

    def collect(self) -> AppConfig:
        raw = {"adapter": self.adapter.currentText().strip(),
               "profiles": [{"name": p.name, "ip": p.ip, "prefix": p.prefix, "gateway": p.gateway,
                             "dns": list(p.dns)} for p in self.profiles]}
        return parse_config(raw, "perfiles")

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


class NotificationsPage(_Page):
    def __init__(self, window: "SettingsWindow", test: Callable[[], None]):
        super().__init__("gauge", "Notificaciones", "Aviso de Windows cuando un plan de IA está por agotarse.")
        self.window = window
        frame, group = _group()
        self.enabled = _switch(window.config.notify, "Notificaciones activadas")
        self.threshold = QSpinBox()
        self.threshold.setRange(50, 100)
        self.threshold.setSuffix(" %")
        self.threshold.setValue(window.config.notify_threshold)
        _row(group, "settings", "Notificaciones activadas", "", self.enabled)
        _row(group, "gauge", "Avisar cuando el uso llegue a", "Una vez por ciclo de reinicio de cada plan.",
             self.threshold)
        self.page_layout.addWidget(frame)
        self.page_layout.addStretch(1)
        self.message = _message()
        self.test_button = _button("Probar notificación")
        self.test_button.clicked.connect(lambda: test())
        self.save_button = _button("Guardar", primary=True)
        self.save_button.clicked.connect(self.save)
        _footer(self.page_layout, self.message, self.test_button, self.save_button)

    def save(self) -> None:
        self.window.save_dock(notify=self.enabled.isChecked(), notify_threshold=self.threshold.value())
        self.message.setText("Guardado.")


class AppearancePage(_Page):
    def __init__(self, window: "SettingsWindow"):
        super().__init__("palette", "Apariencia", "Dónde se pega la gota y cómo se comporta.")
        self.window = window
        frame, group = _group()
        self.edge = QComboBox()
        for label, value in EDGE_LABELS:
            self.edge.addItem(label, value)
        self.edge.setCurrentIndex(self.edge.findData(window.config.edge))
        self.width = QSpinBox()
        self.width.setRange(280, 480)
        self.width.setSingleStep(10)
        self.width.setSuffix(" px")
        self.width.setValue(window.config.width)
        self.liquid = _switch(window.config.liquid, "Efecto líquido")
        self.show_dock = _switch(window.config.show_dock, "Mostrar barra en el borde")
        _row(group, "palette", "Borde de la pantalla", "Dónde se pega la barra.", self.edge)
        _row(group, "palette", "Ancho de las apps", "", self.width)
        _row(group, "palette", "Efecto líquido", "Ondas al abrir y al pasar el mouse.", self.liquid)
        _row(group, "palette", "Barra en el borde",
             "Apagada, las apps se abren solo desde el ícono de la bandeja.", self.show_dock)
        self.page_layout.addWidget(frame)
        self.page_layout.addStretch(1)
        self.message = _message()
        self.save_button = _button("Guardar", primary=True)
        self.save_button.clicked.connect(self.save)
        _footer(self.page_layout, self.message, self.save_button)

    def save(self) -> None:
        self.window.save_dock(edge=self.edge.currentData(), width=self.width.value(),
                              liquid=self.liquid.isChecked(), show_dock=self.show_dock.isChecked())
        self.message.setText("Guardado.")


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
        available_tools: Sequence[tuple[str, str]] = (("ip_switch", "Cambio de IP"), ("ai_usage", "Uso de IA")),
        test_notification: Callable[[], None] = lambda: None,
        usage_probe: UsageProbe = lambda source, config: None,
    ):
        super().__init__(None, Qt.WindowType.Window)
        self.setWindowTitle(f"{APP_NAME} · Configuración")
        self.setStyleSheet(STYLE)
        self.resize(900, 580)
        self.config = config
        self._on_dock_save = on_dock_save
        layout = QHBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(0)

        sidebar = QWidget()
        sidebar.setObjectName("sidebar")
        sidebar.setFixedWidth(220)
        side = QVBoxLayout(sidebar)
        side.setContentsMargins(14, 18, 14, 14)
        side.setSpacing(12)
        brand = QHBoxLayout()
        brand.setSpacing(10)
        brand.addWidget(_icon_label("settings", 20, "#ffffff"))
        title = QLabel("Configuración")
        title.setObjectName("sidebarTitle")
        brand.addWidget(title, 1)
        side.addLayout(brand)
        self.nav = QListWidget()
        self.nav.setIconSize(QSize(17, 17))
        side.addWidget(self.nav, 1)

        self.stack = QStackedWidget()
        self.general = GeneralPage(self, available_tools)
        self.ai = AiPage(self, statusline_installed, statusline_install, statusline_uninstall, usage_probe, run)
        self.network = NetworkPage(self, ip_load, ip_adapters, ip_save, run)
        self.notifications = NotificationsPage(self, test_notification)
        self.appearance = AppearancePage(self)
        self._pages = {
            "General": (self.general, "settings"),
            "Planes de IA": (self.ai, "bot"),
            "Red (IP)": (self.network, "network"),
            "Notificaciones": (self.notifications, "gauge"),
            "Apariencia": (self.appearance, "palette"),
        }
        for name, (page, icon) in self._pages.items():
            item = QListWidgetItem(name)
            svg = svg_icon(icon, size=17)
            if svg is not None:
                item.setIcon(svg)
            self.nav.addItem(item)
            page.layout().setContentsMargins(28, 24, 28, 22)
            self.stack.addWidget(page)
        self.nav.currentRowChanged.connect(self.stack.setCurrentIndex)
        self.nav.setCurrentRow(0)
        layout.addWidget(sidebar)
        layout.addWidget(self.stack, 1)

    def showEvent(self, event) -> None:
        super().showEvent(event)
        dark_title_bar(int(self.winId()))

    def section_names(self) -> list[str]:
        return list(self._pages)

    def show_section(self, name: str) -> None:
        self.nav.setCurrentRow(self.section_names().index(name))

    def save_dock(self, **changes) -> None:
        self.config = replace(self.config, **changes)
        self._on_dock_save(self.config)
