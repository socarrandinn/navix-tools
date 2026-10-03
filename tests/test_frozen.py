"""Rutas y comandos cuando IPDock corre instalado (PyInstaller), no desde el código fuente."""

from pathlib import Path

from ipswitch.config import AppConfig
from ipswitch.elevate import decode_config, save_config_command
from ipswitch.frozen import app_dir, dock_exe, cli_exe
from ipswitch.install import helper_action_frozen
from ipswitch.models import StaticProfile

APP = Path(r"C:\Program Files\IPDock")
CONFIG = AppConfig("Wi-Fi", (StaticProfile("Casa", "192.168.0.100", 24, "192.168.0.254", ()),))


def test_app_dir_from_either_executable():
    assert app_dir(APP / "IPDock.exe") == APP
    assert app_dir(APP / "cli" / "ipswitch.exe") == APP
    assert dock_exe(APP / "cli" / "ipswitch.exe") == APP / "IPDock.exe"
    assert cli_exe(APP / "IPDock.exe") == APP / "cli" / "ipswitch.exe"


def test_helper_task_runs_the_installed_windowed_exe():
    assert helper_action_frozen(APP / "cli" / "ipswitch.exe") == (str(APP / "IPDock.exe"), "helper", str(APP))


def test_save_config_uses_installed_exe_when_frozen():
    exe, params, cwd = save_config_command(CONFIG, executable=str(APP / "IPDock.exe"), frozen=True)
    assert exe == str(APP / "IPDock.exe")
    assert params.startswith("save-config ")
    assert decode_config(params.split()[-1]) == CONFIG
    assert cwd == str(APP)


def test_statusline_recorder_uses_console_cli_when_frozen():
    from dock.statusline import recorder_command_for

    assert recorder_command_for(True, str(APP / "IPDock.exe")) == f'"{APP / "cli" / "ipswitch.exe"}" statusline'


def test_frozen_install_registers_installed_exe_without_copying_python(tmp_path):
    import base64

    from ipswitch.install import install
    from ipswitch.shell import CommandResult

    scripts = []

    def runner(args):
        scripts.append(base64.b64decode(args[4]).decode("utf-16-le"))
        return CommandResult(0, "")

    app = tmp_path / "IPDock"
    (app / "cli").mkdir(parents=True)
    install(config_path=tmp_path / "ProgramData" / "ipswitch" / "config.json", runner=runner,
            frozen=True, executable=str(app / "cli" / "ipswitch.exe"))
    register = scripts[-1]
    assert f"-Execute '{app / 'IPDock.exe'}'" in register
    assert "-Argument 'helper'" in register
    assert not (app / "python").exists()


def test_dock_run_dispatches_commands(monkeypatch):
    import dock_run

    calls = []
    monkeypatch.setattr("ipswitch.__main__.main", lambda argv: calls.append(("cli", argv)) or 0)
    monkeypatch.setattr("dock.__main__.main", lambda argv: calls.append(("dock", argv)) or 0)
    assert dock_run.main(["helper"]) == 0
    assert dock_run.main(["save-config", "abc"]) == 0
    assert dock_run.main([]) == 0
    assert calls == [("cli", ["helper"]), ("cli", ["save-config", "abc"]), ("dock", [])]


def test_cli_entry_routes_statusline(monkeypatch):
    import ipswitch_cli

    calls = []
    monkeypatch.setattr("dock.statusline.main", lambda argv: calls.append(("statusline", argv)) or 0)
    monkeypatch.setattr("ipswitch.__main__.main", lambda argv: calls.append(("cli", argv)) or 0)
    assert ipswitch_cli.main(["statusline"]) == 0
    assert ipswitch_cli.main(["status"]) == 0
    assert calls == [("statusline", []), ("cli", ["status"])]
