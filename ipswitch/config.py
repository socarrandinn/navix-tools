from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path

from .models import ProfileError, StaticProfile
from .paths import FOLDERID_PROGRAM_DATA, known_folder


class ConfigError(Exception):
    pass


@dataclass(frozen=True)
class AppConfig:
    adapter: str
    profiles: tuple[StaticProfile, ...]


DEFAULT_CONFIG = AppConfig(
    adapter="Wi-Fi",
    profiles=(
        StaticProfile("Casa", "192.168.0.100", 24, "192.168.0.254", ("192.168.0.254", "8.8.8.8")),
    ),
)


def default_config_path() -> Path:
    return known_folder(FOLDERID_PROGRAM_DATA) / "ipswitch" / "config.json"


def save_config(path: Path, config: AppConfig) -> None:
    data = {
        "adapter": config.adapter,
        "profiles": [
            {"name": p.name, "ip": p.ip, "prefix": p.prefix, "gateway": p.gateway, "dns": list(p.dns)}
            for p in config.profiles
        ],
    }
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(data, indent=2, ensure_ascii=False), encoding="utf-8")


def ensure_config(path: Path) -> None:
    if not path.exists():
        save_config(path, DEFAULT_CONFIG)


def load_config(path: Path) -> AppConfig:
    if not path.exists():
        raise ConfigError(
            f"No existe {path}. En una terminal de administrador ejecuta: python -m ipswitch install"
        )
    try:
        raw = json.loads(path.read_text(encoding="utf-8"))
        adapter = str(raw["adapter"]).strip()
        profiles = tuple(
            StaticProfile(
                name=str(p["name"]).strip(),
                ip=str(p["ip"]).strip(),
                prefix=int(p["prefix"]),
                gateway=str(p["gateway"]).strip(),
                dns=tuple(str(d).strip() for d in p.get("dns", [])),
            )
            for p in raw["profiles"]
        )
    except (OSError, ValueError, KeyError, TypeError) as exc:
        raise ConfigError(f"No se pudo leer {path}: falta o es inválido {exc}") from exc
    if not adapter:
        raise ConfigError(f"{path}: el adaptador no puede estar vacío")
    seen: set[str] = set()
    for profile in profiles:
        try:
            profile.validate()
        except ProfileError as exc:
            raise ConfigError(f"{path}: {exc}") from exc
        if profile.name in seen:
            raise ConfigError(f"{path}: nombre de perfil duplicado: {profile.name}")
        seen.add(profile.name)
    return AppConfig(adapter=adapter, profiles=profiles)
