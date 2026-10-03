from __future__ import annotations

import json
import os
import re
from dataclasses import asdict, dataclass
from pathlib import Path

TOOL_NAME = re.compile(r"^[a-z][a-z0-9_]*$")
EDGES = {"left", "right", "top"}
AI_SOURCES = ("claude", "codex")


class DockConfigError(Exception):
    pass


@dataclass(frozen=True)
class DockConfig:
    edge: str = "right"
    width: int = 320
    tools: tuple[str, ...] = ("ip_switch", "ai_usage")
    pinned: bool = False
    position: float = 0.5
    ai_sources: tuple[str, ...] = AI_SOURCES
    liquid: bool = True
    notify: bool = True
    notify_threshold: int = 85


def dock_dir() -> Path:
    base = os.environ.get("APPDATA") or str(Path.home())
    return Path(base) / "ipdock"


def save_dock_config(path: Path, config: DockConfig) -> None:
    data = asdict(config)
    data["tools"] = list(config.tools)
    data["ai_sources"] = list(config.ai_sources)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(data, indent=2), encoding="utf-8")


def load_dock_config(path: Path) -> DockConfig:
    if not path.exists():
        config = DockConfig()
        save_dock_config(path, config)
        return config
    try:
        raw = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, ValueError) as exc:
        raise DockConfigError(f"No se pudo leer {path}: {exc}") from exc
    if not isinstance(raw, dict):
        raise DockConfigError(f"{path}: debe ser un objeto JSON")
    default = DockConfig()
    edge = raw.get("edge", default.edge)
    if edge not in EDGES:
        raise DockConfigError(f"{path}: edge debe ser left, right o top, no {edge!r}")
    width = raw.get("width", default.width)
    if not isinstance(width, int) or not 200 <= width <= 600:
        raise DockConfigError(f"{path}: width debe ser un entero entre 200 y 600")
    tools = raw.get("tools", list(default.tools))
    if not isinstance(tools, list):
        raise DockConfigError(f"{path}: tools debe ser una lista")
    for name in tools:
        if not isinstance(name, str) or not TOOL_NAME.match(name):
            raise DockConfigError(f"{path}: nombre de herramienta inválido: {name!r}")
    pinned = raw.get("pinned", default.pinned)
    if not isinstance(pinned, bool):
        raise DockConfigError(f"{path}: pinned debe ser true o false")
    position = raw.get("position", default.position)
    if isinstance(position, bool) or not isinstance(position, (int, float)) or not 0 <= position <= 1:
        raise DockConfigError(f"{path}: position debe ser un número entre 0 y 1")
    ai_sources = raw.get("ai_sources", list(default.ai_sources))
    if not isinstance(ai_sources, list) or any(s not in AI_SOURCES for s in ai_sources):
        raise DockConfigError(f"{path}: ai_sources debe ser una lista con claude y/o codex")
    liquid = raw.get("liquid", default.liquid)
    if not isinstance(liquid, bool):
        raise DockConfigError(f"{path}: liquid debe ser true o false")
    notify = raw.get("notify", default.notify)
    if not isinstance(notify, bool):
        raise DockConfigError(f"{path}: notify debe ser true o false")
    threshold = raw.get("notify_threshold", default.notify_threshold)
    if isinstance(threshold, bool) or not isinstance(threshold, int) or not 50 <= threshold <= 100:
        raise DockConfigError(f"{path}: notify_threshold debe ser un entero entre 50 y 100")
    return DockConfig(edge=edge, width=width, tools=tuple(tools), pinned=pinned,
                      position=float(position), ai_sources=tuple(ai_sources), liquid=liquid,
                      notify=notify, notify_threshold=threshold)
