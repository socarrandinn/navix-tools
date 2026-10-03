import json

import pytest

from dock.config import DockConfig, DockConfigError, dock_dir, load_dock_config, save_dock_config


def test_missing_creates_default(tmp_path):
    path = tmp_path / "ipdock" / "dock.json"
    assert load_dock_config(path) == DockConfig()
    assert json.loads(path.read_text(encoding="utf-8"))["tools"] == ["ip_switch"]


def test_roundtrip(tmp_path):
    path = tmp_path / "dock.json"
    config = DockConfig(edge="left", width=400, backdrop="none", tools=("subscriptions",), pinned=True, position=0.25)
    save_dock_config(path, config)
    assert load_dock_config(path) == config


def test_partial_file_uses_defaults(tmp_path):
    path = tmp_path / "dock.json"
    path.write_text('{"edge": "left"}', encoding="utf-8")
    assert load_dock_config(path) == DockConfig(edge="left")


@pytest.mark.parametrize(
    "data, fragment",
    [
        ({"edge": "top"}, "edge"),
        ({"width": 50}, "width"),
        ({"width": "ancho"}, "width"),
        ({"backdrop": "glass"}, "backdrop"),
        ({"tools": ["../os"]}, "herramienta"),
        ({"tools": "ip_switch"}, "tools"),
        ([1], "dock.json"),
        ({"pinned": "si"}, "pinned"),
        ({"position": 1.5}, "position"),
        ({"position": "arriba"}, "position"),
    ],
)
def test_invalid_config_raises(tmp_path, data, fragment):
    path = tmp_path / "dock.json"
    path.write_text(json.dumps(data), encoding="utf-8")
    with pytest.raises(DockConfigError, match=fragment):
        load_dock_config(path)


def test_corrupt_not_overwritten(tmp_path):
    path = tmp_path / "dock.json"
    path.write_text("{roto", encoding="utf-8")
    with pytest.raises(DockConfigError):
        load_dock_config(path)
    assert path.read_text(encoding="utf-8") == "{roto"


def test_dock_dir_uses_appdata(monkeypatch, tmp_path):
    monkeypatch.setenv("APPDATA", str(tmp_path))
    assert dock_dir() == tmp_path / "ipdock"


def test_defaults_bubble_middle_unpinned():
    assert DockConfig().pinned is False
    assert DockConfig().position == 0.5


def test_integer_position_accepted(tmp_path):
    path = tmp_path / "dock.json"
    path.write_text('{"position": 1}', encoding="utf-8")
    assert load_dock_config(path).position == 1.0
