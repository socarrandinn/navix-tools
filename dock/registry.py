from __future__ import annotations

import importlib
from dataclasses import dataclass
from typing import Callable, Sequence

from .config import TOOL_NAME
from .tool import Tool


@dataclass(frozen=True)
class LoadedTool:
    name: str
    tool: Tool | None
    error: str | None


def load_tools(names: Sequence[str], importer: Callable = importlib.import_module) -> list[LoadedTool]:
    loaded = []
    for name in names:
        if not TOOL_NAME.match(name):
            loaded.append(LoadedTool(name, None, f"Nombre de herramienta inválido: {name!r}"))
            continue
        try:
            module = importer(f"dock.tools.{name}")
            factory = getattr(module, "create_tool", None)
            if factory is None:
                raise AttributeError(f"dock.tools.{name} no define create_tool()")
            tool = factory()
        except Exception as exc:  # noqa: BLE001 - una herramienta rota no tumba el panel
            loaded.append(LoadedTool(name, None, f"{type(exc).__name__}: {exc}"))
            continue
        if not isinstance(tool, Tool):
            loaded.append(LoadedTool(name, None, f"create_tool() de {name} no devolvió un Tool"))
            continue
        loaded.append(LoadedTool(name, tool, None))
    return loaded
