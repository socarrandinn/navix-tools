from dataclasses import replace

from PySide6.QtCore import Qt

from dock.config import DockConfig
from dock.settings import SettingsWindow
from ipswitch.config import AppConfig, ConfigError
from ipswitch.models import StaticProfile

CASA = StaticProfile("Casa", "192.168.0.100", 24, "192.168.0.254", ("192.168.0.254", "8.8.8.8"))
IP_CONFIG = AppConfig("Wi-Fi", (CASA,))


def run_sync(fn, on_done, on_error):
    try:
        value = fn()
    except Exception as exc:  # noqa: BLE001
        on_error(exc)
    else:
        on_done(value)


class Harness:
    def __init__(self, qtbot, ip_load=None, ip_save=None, installed=False):
        self.dock_saved = []
        self.ip_saved = []
        self.installed = installed
        self.install_calls = []

        def default_ip_save(config):
            self.ip_saved.append(config)

        def install():
            self.install_calls.append("install")
            self.installed = True

        def uninstall():
            self.install_calls.append("uninstall")
            self.installed = False

        self.window = SettingsWindow(
            DockConfig(),
            on_dock_save=self.dock_saved.append,
            ip_load=ip_load or (lambda: IP_CONFIG),
            ip_adapters=lambda: ["Wi-Fi", "Ethernet"],
            ip_save=ip_save or default_ip_save,
            statusline_installed=lambda: self.installed,
            statusline_install=install,
            statusline_uninstall=uninstall,
            run=run_sync,
        )
        qtbot.addWidget(self.window)


def test_window_has_three_sections(qtbot):
    h = Harness(qtbot)
    assert h.window.section_names() == ["Planes de IA", "Red (IP)", "Apariencia"]
    h.window.show_section("Red (IP)")
    assert h.window.stack.currentWidget() is h.window.network


def test_appearance_saves_edge_width_and_liquid(qtbot):
    h = Harness(qtbot)
    page = h.window.appearance
    page.edge.setCurrentIndex(page.edge.findData("top"))
    page.width.setValue(360)
    page.liquid.setChecked(False)
    qtbot.mouseClick(page.save_button, Qt.MouseButton.LeftButton)
    assert h.dock_saved[-1] == replace(DockConfig(), edge="top", width=360, liquid=False)


def test_ai_page_toggles_sources(qtbot):
    h = Harness(qtbot)
    page = h.window.ai
    assert page.claude.isChecked() and page.codex.isChecked()
    page.codex.setChecked(False)
    qtbot.mouseClick(page.save_button, Qt.MouseButton.LeftButton)
    assert h.dock_saved[-1].ai_sources == ("claude",)


def test_ai_page_installs_and_removes_claude_recorder(qtbot):
    h = Harness(qtbot)
    page = h.window.ai
    assert page.statusline_button.text() == "Activar"
    qtbot.mouseClick(page.statusline_button, Qt.MouseButton.LeftButton)
    assert h.install_calls == ["install"]
    assert page.statusline_button.text() == "Desactivar"
    qtbot.mouseClick(page.statusline_button, Qt.MouseButton.LeftButton)
    assert h.install_calls == ["install", "uninstall"]


def test_network_page_loads_profiles_and_adapters(qtbot):
    h = Harness(qtbot)
    page = h.window.network
    assert page.adapter.currentText() == "Wi-Fi"
    assert page.table.rowCount() == 1
    assert [page.table.item(0, c).text() for c in range(5)] == [
        "Casa", "192.168.0.100", "24", "192.168.0.254", "192.168.0.254, 8.8.8.8"]


def test_network_page_add_profile_and_save(qtbot):
    h = Harness(qtbot)
    page = h.window.network
    qtbot.mouseClick(page.add_button, Qt.MouseButton.LeftButton)
    for column, value in enumerate(["Oficina", "10.0.0.50", "24", "10.0.0.1", "10.0.0.1"]):
        page.table.item(1, column).setText(value)
    qtbot.mouseClick(page.save_button, Qt.MouseButton.LeftButton)
    saved = h.ip_saved[-1]
    assert [p.name for p in saved.profiles] == ["Casa", "Oficina"]
    assert saved.profiles[1] == StaticProfile("Oficina", "10.0.0.50", 24, "10.0.0.1", ("10.0.0.1",))
    assert "Guardado" in page.message.text()


def test_network_page_remove_profile(qtbot):
    h = Harness(qtbot)
    page = h.window.network
    page.table.selectRow(0)
    qtbot.mouseClick(page.remove_button, Qt.MouseButton.LeftButton)
    assert page.table.rowCount() == 0


def test_invalid_profile_is_rejected_before_asking_for_admin(qtbot):
    h = Harness(qtbot)
    page = h.window.network
    page.table.item(0, 3).setText("10.0.0.1")
    qtbot.mouseClick(page.save_button, Qt.MouseButton.LeftButton)
    assert h.ip_saved == []
    assert "fuera" in page.message.text()


def test_save_failure_is_shown(qtbot):
    def ip_save(config):
        raise ConfigError("Guardado cancelado: se necesita permiso de administrador.")

    h = Harness(qtbot, ip_save=ip_save)
    qtbot.mouseClick(h.window.network.save_button, Qt.MouseButton.LeftButton)
    assert "cancelado" in h.window.network.message.text()


def test_network_page_without_install_explains_and_disables_save(qtbot):
    def ip_load():
        raise ConfigError("No existe config. python -m ipswitch install")

    h = Harness(qtbot, ip_load=ip_load)
    page = h.window.network
    assert "install" in page.message.text()
    assert not page.save_button.isEnabled()


def test_empty_rows_are_ignored(qtbot):
    h = Harness(qtbot)
    page = h.window.network
    qtbot.mouseClick(page.add_button, Qt.MouseButton.LeftButton)
    qtbot.mouseClick(page.save_button, Qt.MouseButton.LeftButton)
    assert [p.name for p in h.ip_saved[-1].profiles] == ["Casa"]


def test_partial_row_names_the_profile(qtbot):
    h = Harness(qtbot)
    page = h.window.network
    qtbot.mouseClick(page.add_button, Qt.MouseButton.LeftButton)
    page.table.item(1, 0).setText("Oficina")
    qtbot.mouseClick(page.save_button, Qt.MouseButton.LeftButton)
    assert h.ip_saved == []
    assert "Oficina" in page.message.text()
