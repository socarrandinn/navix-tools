import json

import pytest

from ipswitch.config import (
    DEFAULT_CONFIG,
    AppConfig,
    ConfigError,
    default_config_path,
    ensure_config,
    load_config,
    save_config,
)
from ipswitch.models import StaticProfile


def test_missing_file_raises_and_mentions_install(tmp_path):
    path = tmp_path / "config.json"
    with pytest.raises(ConfigError, match="install"):
        load_config(path)
    assert not path.exists()


def test_ensure_config_creates_default(tmp_path):
    path = tmp_path / "sub" / "config.json"
    ensure_config(path)
    assert load_config(path) == DEFAULT_CONFIG


def test_ensure_config_keeps_existing(tmp_path):
    path = tmp_path / "config.json"
    path.write_text("{broken", encoding="utf-8")
    ensure_config(path)
    assert path.read_text(encoding="utf-8") == "{broken"


def test_default_matches_current_machine():
    assert DEFAULT_CONFIG.adapter == "Wi-Fi"
    (casa,) = DEFAULT_CONFIG.profiles
    assert casa == StaticProfile("Casa", "192.168.0.100", 24, "192.168.0.254", ("192.168.0.254", "8.8.8.8"))


def test_roundtrip_with_non_ascii(tmp_path):
    path = tmp_path / "config.json"
    config = AppConfig(
        adapter="Conexión de área local* 1",
        profiles=(StaticProfile("Oficina", "10.0.0.5", 8, "10.0.0.1", ()),),
    )
    save_config(path, config)
    assert load_config(path) == config


def test_values_are_stripped(tmp_path):
    path = tmp_path / "config.json"
    path.write_text(
        json.dumps({"adapter": " Wi-Fi ", "profiles": [
            {"name": " Casa ", "ip": " 192.168.0.100", "prefix": "24", "gateway": "192.168.0.254 ", "dns": [" 8.8.8.8 "]}
        ]}),
        encoding="utf-8",
    )
    config = load_config(path)
    assert config.adapter == "Wi-Fi"
    assert config.profiles[0] == StaticProfile("Casa", "192.168.0.100", 24, "192.168.0.254", ("8.8.8.8",))


def test_corrupt_config_raises_and_is_not_overwritten(tmp_path):
    path = tmp_path / "config.json"
    path.write_text("{not json", encoding="utf-8")
    with pytest.raises(ConfigError, match="config.json"):
        load_config(path)
    assert path.read_text(encoding="utf-8") == "{not json"


@pytest.mark.parametrize(
    "data, fragment",
    [
        ({"profiles": []}, "adapter"),
        ({"adapter": "", "profiles": []}, "adaptador"),
        ({"adapter": "Wi-Fi", "profiles": [{"name": "X"}]}, "ip"),
        ({"adapter": "Wi-Fi", "profiles": [
            {"name": "X", "ip": "192.168.0.10", "prefix": 24, "gateway": "10.0.0.1"}]}, "fuera"),
        ({"adapter": "Wi-Fi", "profiles": [
            {"name": "X", "ip": "192.168.0.10", "prefix": 24, "gateway": "192.168.0.1"},
            {"name": "X", "ip": "192.168.0.11", "prefix": 24, "gateway": "192.168.0.1"}]}, "duplicado"),
        ([1, 2], "config.json"),
    ],
)
def test_invalid_config_raises(tmp_path, data, fragment):
    path = tmp_path / "config.json"
    path.write_text(json.dumps(data), encoding="utf-8")
    with pytest.raises(ConfigError, match=fragment):
        load_config(path)


def test_default_config_path_uses_programdata(monkeypatch, tmp_path):
    monkeypatch.setenv("ProgramData", str(tmp_path))
    assert default_config_path() == tmp_path / "ipswitch" / "config.json"
