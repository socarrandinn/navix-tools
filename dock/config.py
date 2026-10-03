from __future__ import annotations

import json
import os
import re
from dataclasses import asdict, dataclass
from pathlib import Path

TOOL_NAME = re.compile(r"^[a-z][a-z0-9_]*$")
EDGES = {"left", "right"}
BACKDROPS = {"acrylic", "none"}


class DockConfigError(Exception):
    pass


@dataclass(frozen=True)
class DockConfig:
    edge: str = "right"
    width: int = 320
    backdrop: str = "acrylic"
    tools: tuple[str, ...] = ("ip_switch", "ai_usage")
    pinned: bool = False
    position: float = 0.5


def dock_dir() -> Path:
    base = os.environ.get("APPDATA") or str(Path.home())
    return Path(base) / "ipdock"


def save_dock_config(path: Path, config: DockConfig) -> None:
    data = asdict(config)
    data["tools"] = list(config.tools)
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
        raise DockConfigError(f"{path}: edge debe ser left o right, no {edge!r}")
    width = raw.get("width", default.width)
    if not isinstance(width, int) or not 200 <= width <= 600:
        raise DockConfigError(f"{path}: width debe ser un entero entre 200 y 600")
    backdrop = raw.get("backdrop", default.backdrop)
    if backdrop not in BACKDROPS:
        raise DockConfigError(f"{path}: backdrop debe ser acrylic o none")
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
    return DockConfig(edge=edge, width=width, backdrop=backdrop, tools=tuple(tools),
                      pinned=pinned, position=float(position))
