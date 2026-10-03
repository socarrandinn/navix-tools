from PySide6.QtCore import Qt

from dock.tools.ip_switch import BLUE, GREEN, IpSwitchTool, create_tool
from ipswitch.client import HelperError
from ipswitch.config import AppConfig, ConfigError
from ipswitch.helper import Result
from ipswitch.models import StaticProfile
from ipswitch.status import AdapterStatus

CASA = StaticProfile("Casa", "192.168.0.100", 24, "192.168.0.254", ("192.168.0.254",))
CONFIG = AppConfig("Wi-Fi", (CASA,))
STATIC = AdapterStatus(False, "192.168.0.100", 24, "192.168.0.254", ("192.168.0.254",))
DHCP = AdapterStatus(True, "192.168.0.57", 24, "192.168.0.254", ("192.168.0.254",))


def run_sync(fn, on_done, on_error):
    try:
        value = fn()
    except Exception as exc:  # noqa: BLE001
        on_error(exc)
    else:
        on_done(value)


class Deferred:
    def __init__(self):
        self.pending = []

    def __call__(self, fn, on_done, on_error):
        self.pending.append((fn, on_done, on_error))

    def finish_next(self):
        run_sync(*self.pending.pop(0))


def make(qtbot, load=lambda: CONFIG, read=None, switch=None, run=run_sync):
    reads = []

    def default_read(adapter):
        reads.append(adapter)
        return STATIC

    tool = IpSwitchTool(load=load, read=read or default_read,
                        switch=switch or (lambda action, profile=None: Result("1", True, "ok")), run=run)
    widget = tool.create_widget()
    qtbot.addWidget(widget)
    # En el panel la tarjeta es dueña del widget; aquí hay que mantenerlo vivo.
    tool.test_widget = widget
    return tool, reads


def test_create_tool_returns_ip_tool():
    assert isinstance(create_tool(), IpSwitchTool)


def test_refresh_shows_active_profile_and_buttons(qtbot):
    tool, _ = make(qtbot)
    tool.refresh()
    assert tool.label.text() == "Fija: Casa"
    assert "192.168.0.100/24" in tool.label.toolTip()
    assert GREEN in tool.dot.styleSheet()
    assert [b.text() for b in tool.buttons] == ["DHCP", "Casa"]


def test_dhcp_status_is_blue(qtbot):
    tool, _ = make(qtbot, read=lambda adapter: DHCP)
    tool.refresh()
    assert tool.label.text() == "DHCP"
    assert BLUE in tool.dot.styleSheet()


def test_click_profile_switches_and_refreshes(qtbot):
    calls = []

    def switch(action, profile=None):
        calls.append((action, profile))
        return Result("1", True, "Perfil Casa aplicado")

    tool, reads = make(qtbot, switch=switch)
    tool.refresh()
    qtbot.mouseClick(tool.buttons[1], Qt.MouseButton.LeftButton)
    assert calls == [("profile", "Casa")]
    assert tool.message.text() == "Perfil Casa aplicado"
    assert len(reads) == 2


def test_buttons_disabled_while_switching_and_refresh_ignored(qtbot):
    deferred = Deferred()
    tool, _ = make(qtbot, run=deferred)
    tool.refresh()
    deferred.finish_next()
    tool.switch("dhcp")
    assert tool.busy is True
    assert not any(b.isEnabled() for b in tool.buttons)
    assert tool.message.text() == "Aplicando…"
    tool.refresh()
    assert len(deferred.pending) == 1
    deferred.finish_next()
    assert tool.busy is False
    assert all(b.isEnabled() for b in tool.buttons)


def test_refreshes_do_not_overlap(qtbot):
    deferred = Deferred()
    tool, _ = make(qtbot, run=deferred)
    tool.refresh()
    tool.refresh()
    assert len(deferred.pending) == 1


def test_switch_failure_shows_message_and_reenables(qtbot):
    def switch(action, profile=None):
        raise HelperError("No se pudo iniciar el helper. python -m ipswitch install")

    tool, _ = make(qtbot, switch=switch)
    tool.refresh()
    tool.switch("dhcp")
    assert "install" in tool.message.text()
    assert all(b.isEnabled() for b in tool.buttons)


def test_config_error_shows_install_hint(qtbot):
    def load():
        raise ConfigError("No existe config. python -m ipswitch install")

    tool, _ = make(qtbot, load=load)
    tool.refresh()
    assert tool.label.text() == "Sin estado"
    assert "install" in tool.message.text()
    assert tool.buttons == []
