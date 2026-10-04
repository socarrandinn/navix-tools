from __future__ import annotations

import sys
from pathlib import Path
from datetime import datetime, timezone

from PySide6.QtCore import QTimer
from PySide6.QtGui import QGuiApplication, QIcon
from PySide6.QtWidgets import QApplication, QMenu, QMessageBox, QSystemTrayIcon

from ipswitch.config import default_config_path, load_config
from ipswitch.elevate import save_config_elevated
from ipswitch.status import list_adapters

from . import statusline
from .brand import APP_NAME
from .config import DockConfig, DockConfigError, dock_dir, load_dock_config, save_dock_config
from .notify import Alert, AlertLog, UsageWatcher
from .panel import Panel, primary_area
from .registry import load_tools
from .settings import SettingsWindow
from .single import acquire_single_instance
from .tray import TrayPanel
from .tools.ai_usage import read_claude_default, read_codex_default
from .worker import run_async

INSTANCE_NAME = "navix-single-instance"
APP_ICON = Path(__file__).resolve().parent / "assets" / "navix.ico"
AVAILABLE_TOOLS = (("ip_switch", "Cambio de IP"), ("ai_usage", "Uso de IA"))
USAGE_CHECK_MS = 5 * 60 * 1000


def configure_app(app: QApplication) -> None:
    # La barra es una ventana de herramienta: Qt no la cuenta, así que al cerrar Configuración
    # (la única ventana normal) terminaba la app. Se sale solo con ✕ o Salir.
    app.setQuitOnLastWindowClosed(False)


def _now() -> datetime:
    return datetime.now(timezone.utc)


def main(argv: list[str] | None = None) -> int:
    app = QApplication(sys.argv[:1])
    configure_app(app)
    app.setApplicationDisplayName(APP_NAME)
    app.setWindowIcon(QIcon(str(APP_ICON)))
    server = acquire_single_instance(INSTANCE_NAME)
    if server is None:
        return 0
    config_path = dock_dir() / "dock.json"
    try:
        config = load_dock_config(config_path)
    except DockConfigError as exc:
        QMessageBox.critical(None, APP_NAME, str(exc))
        return 1

    state: dict[str, object] = {}
    # Una instalación anterior (IPDock) dejó la status line apuntando a su carpeta.
    statusline.refresh_command(statusline.settings_path(), statusline.default_recorder_command())

    def current() -> Panel:
        return state["panel"]  # type: ignore[return-value]

    def build_panel(dock_config: DockConfig) -> Panel:
        panel = Panel(dock_config, load_tools(dock_config.tools), primary_area,
                      on_config_change=lambda changed: save_dock_config(config_path, changed),
                      on_settings=open_settings)
        QGuiApplication.primaryScreen().availableGeometryChanged.connect(panel.reposition)
        panel.setVisible(dock_config.show_dock)
        return panel

    def save_and_apply(changed: DockConfig) -> None:
        save_dock_config(config_path, changed)
        old = current()
        if changed.tools != old.config.tools or changed.width != old.config.width:
            stale = state.pop("tray_panel", None)  # se rearma con las apps y el ancho nuevos
            if stale is not None:
                stale.close()
                stale.deleteLater()
        if changed.tools != old.config.tools:
            # Cambiaron las apps de la barra: se arma una barra nueva con las elegidas.
            state["panel"] = build_panel(changed)
            old.close()
            old.deleteLater()
        else:
            old.apply_config(changed)
            old.setVisible(changed.show_dock)

    tray = QSystemTrayIcon(QIcon(str(APP_ICON)))
    tray.setToolTip(APP_NAME)

    def show_alert(alert: Alert) -> None:
        tray.showMessage(alert.title, alert.message, QSystemTrayIcon.MessageIcon.Warning, 8000)

    def test_notification() -> None:
        tray.showMessage(APP_NAME, "Así se ven los avisos de planes por agotarse.",
                         QSystemTrayIcon.MessageIcon.Information, 5000)

    def open_settings() -> None:
        window = state.get("settings")
        if window is None:
            recorder = statusline.default_recorder_command()
            window = SettingsWindow(
                current().config,
                on_dock_save=save_and_apply,
                ip_load=lambda: load_config(default_config_path()),
                ip_adapters=list_adapters,
                ip_save=save_config_elevated,
                statusline_installed=lambda: statusline.is_installed(statusline.settings_path(), recorder),
                statusline_install=lambda: statusline.install(statusline.settings_path(),
                                                              statusline.chain_path(), recorder),
                statusline_uninstall=lambda: statusline.uninstall(statusline.settings_path(),
                                                                  statusline.chain_path()),
                available_tools=AVAILABLE_TOOLS,
                test_notification=test_notification,
            )
            state["settings"] = window
        window.show()
        window.raise_()
        window.activateWindow()

    tray_menu = QMenu()
    tray_menu.addAction("Configuración").triggered.connect(open_settings)
    tray_menu.addSeparator()
    tray_menu.addAction("Salir").triggered.connect(app.quit)
    tray.setContextMenu(tray_menu)

    def toggle_tray_panel() -> None:
        panel = state.get("tray_panel")
        if panel is None:
            dock_config = current().config
            panel = TrayPanel(load_tools(dock_config.tools), width=dock_config.width)
            state["tray_panel"] = panel
        panel.toggle(primary_area(), tray.geometry())

    def on_tray_activated(reason: QSystemTrayIcon.ActivationReason) -> None:
        if reason == QSystemTrayIcon.ActivationReason.Trigger:
            toggle_tray_panel()

    tray.activated.connect(on_tray_activated)
    tray.show()

    def read_usage():
        sources = current().config.ai_sources
        now = _now()
        return [read_claude_default(now) if "claude" in sources else None,
                read_codex_default(now) if "codex" in sources else None]

    watcher = UsageWatcher(read=read_usage, config=lambda: current().config,
                           log=AlertLog(dock_dir() / "alerts.json"), show=show_alert, now=_now, run=run_async)
    timer = QTimer()
    timer.setInterval(USAGE_CHECK_MS)
    timer.timeout.connect(watcher.check)
    timer.start()
    QTimer.singleShot(15_000, watcher.check)

    state["panel"] = build_panel(config)
    return app.exec()


if __name__ == "__main__":
    raise SystemExit(main())
