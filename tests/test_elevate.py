import base64
import json
from pathlib import Path

import pytest

import ipswitch.__main__ as cli
from ipswitch.config import AppConfig, ConfigError, load_config, parse_config
from ipswitch.elevate import decode_config, encode_config, save_config_command, save_config_elevated
from ipswitch.models import StaticProfile

CASA = StaticProfile("Casa", "192.168.0.100", 24, "192.168.0.254", ("192.168.0.254", "8.8.8.8"))
CONFIG = AppConfig("Wi-Fi", (CASA,))


def test_parse_config_validates_like_load_config():
    assert parse_config({"adapter": "Wi-Fi", "profiles": [
        {"name": "Casa", "ip": "192.168.0.100", "prefix": 24, "gateway": "192.168.0.254",
         "dns": ["192.168.0.254", "8.8.8.8"]}]}, "x") == CONFIG
    with pytest.raises(ConfigError, match="fuera"):
        parse_config({"adapter": "Wi-Fi", "profiles": [
            {"name": "X", "ip": "192.168.0.10", "prefix": 24, "gateway": "10.0.0.1"}]}, "x")


def test_encode_decode_roundtrip_is_command_line_safe():
    text = encode_config(AppConfig("Conexión de área local* 1", (CASA,)))
    assert all(c.isalnum() or c in "-_=" for c in text)
    assert decode_config(text) == AppConfig("Conexión de área local* 1", (CASA,))


def test_decode_rejects_garbage_and_invalid_profiles():
    with pytest.raises(ConfigError):
        decode_config("%%%no-base64")
    bad = base64.urlsafe_b64encode(json.dumps({"adapter": "Wi-Fi", "profiles": [
        {"name": "X", "ip": "1.2.3.400", "prefix": 24, "gateway": "1.2.3.1"}]}).encode()).decode()
    with pytest.raises(ConfigError, match="IP"):
        decode_config(bad)


def test_save_config_command_runs_hidden_pythonw_from_repo(tmp_path):
    (tmp_path / "python.exe").write_text("")
    (tmp_path / "pythonw.exe").write_text("")
    exe, params, cwd = save_config_command(CONFIG, executable=str(tmp_path / "python.exe"))
    assert exe == str(tmp_path / "pythonw.exe")
    assert params.startswith("-m ipswitch save-config ")
    assert decode_config(params.split()[-1]) == CONFIG
    assert Path(cwd, "ipswitch", "__init__.py").exists()


def test_save_config_elevated_reports_cancel_and_failure():
    with pytest.raises(ConfigError, match="cancel"):
        save_config_elevated(CONFIG, runner=lambda exe, params, cwd: -1)
    with pytest.raises(ConfigError, match="código 1"):
        save_config_elevated(CONFIG, runner=lambda exe, params, cwd: 1)
    calls = []
    save_config_elevated(CONFIG, runner=lambda exe, params, cwd: calls.append(params) or 0)
    assert calls


def test_cli_save_config_requires_admin(monkeypatch, capsys):
    monkeypatch.setattr(cli, "is_admin", lambda: False)
    assert cli.main(["save-config", encode_config(CONFIG)]) == 1
    assert "administrador" in capsys.readouterr().err


def test_cli_save_config_writes_admin_config(monkeypatch, tmp_path):
    target = tmp_path / "ipswitch" / "config.json"
    monkeypatch.setattr(cli, "is_admin", lambda: True)
    monkeypatch.setattr(cli, "default_config_path", lambda: target)
    assert cli.main(["save-config", encode_config(CONFIG)]) == 0
    assert load_config(target) == CONFIG


def test_cli_save_config_rejects_invalid(monkeypatch, tmp_path, capsys):
    target = tmp_path / "config.json"
    monkeypatch.setattr(cli, "is_admin", lambda: True)
    monkeypatch.setattr(cli, "default_config_path", lambda: target)
    assert cli.main(["save-config", "basura"]) == 1
    assert not target.exists()
