import ipswitch.__main__ as cli
from ipswitch.client import HelperError
from ipswitch.config import AppConfig, ConfigError
from ipswitch.helper import Result
from ipswitch.models import StaticProfile
from ipswitch.status import AdapterStatus

CASA = StaticProfile("Casa", "192.168.0.100", 24, "192.168.0.254", ("192.168.0.254",))


def test_status_prints_adapter_label_and_details(monkeypatch, capsys):
    monkeypatch.setattr(cli, "load_config", lambda path: AppConfig("Wi-Fi", (CASA,)))
    monkeypatch.setattr(cli, "read_status", lambda adapter: AdapterStatus(
        False, "192.168.0.100", 24, "192.168.0.254", ("192.168.0.254",)))
    assert cli.main(["status"]) == 0
    out = capsys.readouterr().out
    assert "Wi-Fi (Fija: Casa)" in out
    assert "IP:      192.168.0.100/24" in out


def test_dhcp_prints_result(monkeypatch, capsys):
    calls = []
    monkeypatch.setattr(cli, "request_switch", lambda action, profile=None: calls.append((action, profile)) or Result("1", True, "DHCP activado"))
    assert cli.main(["dhcp"]) == 0
    assert calls == [("dhcp", None)]
    assert "DHCP activado" in capsys.readouterr().out


def test_profile_failure_returns_1(monkeypatch, capsys):
    monkeypatch.setattr(cli, "request_switch", lambda action, profile=None: Result("1", False, f"Perfil no encontrado: {profile}"))
    assert cli.main(["profile", "Oficina"]) == 1
    assert "Perfil no encontrado: Oficina" in capsys.readouterr().out


def test_helper_error_returns_1(monkeypatch, capsys):
    def boom(action, profile=None):
        raise HelperError("No se pudo iniciar el helper. python -m ipswitch install")

    monkeypatch.setattr(cli, "request_switch", boom)
    assert cli.main(["dhcp"]) == 1
    assert "install" in capsys.readouterr().err


def test_install_requires_admin(monkeypatch, capsys):
    called = []
    monkeypatch.setattr(cli, "is_admin", lambda: False)
    monkeypatch.setattr(cli, "install", lambda: called.append(True))
    assert cli.main(["install"]) == 1
    assert called == []
    assert "administrador" in capsys.readouterr().err


def test_install_as_admin(monkeypatch, capsys):
    called = []
    monkeypatch.setattr(cli, "is_admin", lambda: True)
    monkeypatch.setattr(cli, "install", lambda: called.append(True) or ["aviso: config.json.untrusted"])
    assert cli.main(["install"]) == 0
    assert called == [True]
    assert "config.json.untrusted" in capsys.readouterr().out


def test_status_config_error_returns_1(monkeypatch, capsys):
    def boom(path):
        raise ConfigError("No existe config. python -m ipswitch install")

    monkeypatch.setattr(cli, "load_config", boom)
    assert cli.main(["status"]) == 1
    assert "install" in capsys.readouterr().err


def test_helper_command_runs_helper(monkeypatch):
    monkeypatch.setattr(cli, "run_helper", lambda requests, results, config_path: [Result("a", True, "ok")])
    assert cli.main(["helper"]) == 0
    monkeypatch.setattr(cli, "run_helper", lambda requests, results, config_path: [Result("a", False, "mal")])
    assert cli.main(["helper"]) == 1
