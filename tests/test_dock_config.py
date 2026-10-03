import json

import pytest

from dock.config import DockConfig, DockConfigError, dock_dir, load_dock_config, save_dock_config


def test_missing_creates_default(tmp_path):
    path = tmp_path / "ipdock" / "dock.json"
    assert load_dock_config(path) == DockConfig()
    assert json.loads(path.read_text(encoding="utf-8"))["tools"] == ["ip_switch", "ai_usage"]


def test_roundtrip(tmp_path):
    path = tmp_path / "dock.json"
    config = DockConfig(edge="left", width=400, tools=("subscriptions",), pinned=True, position=0.25)
    save_dock_config(path, config)
    assert load_dock_config(path) == config


def test_partial_file_uses_defaults(tmp_path):
    path = tmp_path / "dock.json"
    path.write_text('{"edge": "left"}', encoding="utf-8")
    assert load_dock_config(path) == DockConfig(edge="left")


@pytest.mark.parametrize(
    "data, fragment",
    [
        ({"edge": "bottom"}, "edge"),
        ({"width": 50}, "width"),
        ({"width": "ancho"}, "width"),
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


def test_top_edge_is_valid(tmp_path):
    path = tmp_path / "dock.json"
    path.write_text('{"edge": "top"}', encoding="utf-8")
    assert load_dock_config(path).edge == "top"


def test_old_backdrop_key_is_ignored(tmp_path):
    path = tmp_path / "dock.json"
    path.write_text('{"backdrop": "acrylic"}', encoding="utf-8")
    assert load_dock_config(path) == DockConfig()


def test_ai_sources_and_liquid_defaults_and_roundtrip(tmp_path):
    assert DockConfig().ai_sources == ("claude", "codex")
    assert DockConfig().liquid is True
    path = tmp_path / "dock.json"
    save_dock_config(path, DockConfig(ai_sources=("codex",), liquid=False))
    assert load_dock_config(path) == DockConfig(ai_sources=("codex",), liquid=False)


@pytest.mark.parametrize("data, fragment", [
    ({"ai_sources": ["gemini"]}, "ai_sources"),
    ({"ai_sources": "claude"}, "ai_sources"),
    ({"liquid": "si"}, "liquid"),
])
def test_invalid_ai_sources_or_liquid(tmp_path, data, fragment):
    path = tmp_path / "dock.json"
    path.write_text(json.dumps(data), encoding="utf-8")
    with pytest.raises(DockConfigError, match=fragment):
        load_dock_config(path)


def test_notification_settings(tmp_path):
    assert DockConfig().notify is True
    assert DockConfig().notify_threshold == 85
    path = tmp_path / "dock.json"
    save_dock_config(path, DockConfig(notify=False, notify_threshold=70))
    assert load_dock_config(path) == DockConfig(notify=False, notify_threshold=70)


@pytest.mark.parametrize("data, fragment", [
    ({"notify": "si"}, "notify"),
    ({"notify_threshold": 120}, "notify_threshold"),
    ({"notify_threshold": "alto"}, "notify_threshold"),
])
def test_invalid_notification_settings(tmp_path, data, fragment):
    path = tmp_path / "dock.json"
    path.write_text(json.dumps(data), encoding="utf-8")
    with pytest.raises(DockConfigError, match=fragment):
        load_dock_config(path)
