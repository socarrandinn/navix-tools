from types import SimpleNamespace

from PySide6.QtWidgets import QLabel

from dock.registry import load_tools
from dock.tool import Tool


class DummyTool(Tool):
    title = "Dummy"

    def create_widget(self):
        return QLabel("hola")


def fake_importer(modules):
    def importer(name):
        value = modules[name]
        if isinstance(value, Exception):
            raise value
        return value
    return importer


def test_load_tools_success():
    importer = fake_importer({"dock.tools.dummy": SimpleNamespace(create_tool=DummyTool)})
    (loaded,) = load_tools(["dummy"], importer=importer)
    assert loaded.name == "dummy"
    assert isinstance(loaded.tool, DummyTool)
    assert loaded.error is None


def test_load_tools_isolates_failures():
    def boom():
        raise ValueError("config rota")

    importer = fake_importer({
        "dock.tools.ok": SimpleNamespace(create_tool=DummyTool),
        "dock.tools.missing": ModuleNotFoundError("No module named 'dock.tools.missing'"),
        "dock.tools.noentry": SimpleNamespace(),
        "dock.tools.raises": SimpleNamespace(create_tool=boom),
        "dock.tools.wrongtype": SimpleNamespace(create_tool=lambda: "no soy tool"),
    })
    loaded = load_tools(["ok", "missing", "noentry", "raises", "wrongtype", "../os"], importer=importer)
    assert [item.name for item in loaded] == ["ok", "missing", "noentry", "raises", "wrongtype", "../os"]
    assert loaded[0].error is None
    assert "ModuleNotFoundError" in loaded[1].error
    assert "create_tool" in loaded[2].error
    assert "config rota" in loaded[3].error
    assert "Tool" in loaded[4].error
    assert "inválido" in loaded[5].error
    assert all(item.tool is None for item in loaded[1:])
