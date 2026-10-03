from __future__ import annotations

import sys

from PySide6.QtGui import QGuiApplication
from PySide6.QtWidgets import QApplication, QMessageBox

from ipswitch.config import default_config_path, load_config
from ipswitch.elevate import save_config_elevated
from ipswitch.status import list_adapters

from . import statusline
from .config import DockConfig, DockConfigError, dock_dir, load_dock_config, save_dock_config
from .panel import Panel, primary_area
from .registry import load_tools
from .settings import SettingsWindow
from .single import acquire_single_instance

INSTANCE_NAME = "ipdock-single-instance"


def main(argv: list[str] | None = None) -> int:
    app = QApplication(sys.argv[:1])
    server = acquire_single_instance(INSTANCE_NAME)
    if server is None:
        return 0
    config_path = dock_dir() / "dock.json"
    try:
        config = load_dock_config(config_path)
    except DockConfigError as exc:
        QMessageBox.critical(None, "IPDock", str(exc))
        return 1

    windows: dict[str, SettingsWindow] = {}

    def save_and_apply(changed: DockConfig) -> None:
        save_dock_config(config_path, changed)
        panel.apply_config(changed)

    def open_settings() -> None:
        window = windows.get("settings")
        if window is None:
            recorder = statusline.default_recorder_command()
            window = SettingsWindow(
                panel.config,
                on_dock_save=save_and_apply,
                ip_load=lambda: load_config(default_config_path()),
                ip_adapters=list_adapters,
                ip_save=save_config_elevated,
                statusline_installed=lambda: statusline.is_installed(statusline.settings_path(), recorder),
                statusline_install=lambda: statusline.install(statusline.settings_path(),
                                                              statusline.chain_path(), recorder),
                statusline_uninstall=lambda: statusline.uninstall(statusline.settings_path(),
                                                                  statusline.chain_path()),
            )
            windows["settings"] = window
        window.show()
        window.raise_()
        window.activateWindow()

    panel = Panel(config, load_tools(config.tools), primary_area,
                  on_config_change=lambda changed: save_dock_config(config_path, changed),
                  on_settings=open_settings)
    QGuiApplication.primaryScreen().availableGeometryChanged.connect(panel.reposition)
    panel.show()
    return app.exec()


if __name__ == "__main__":
    raise SystemExit(main())
