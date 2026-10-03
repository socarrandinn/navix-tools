from __future__ import annotations

import json
import os
from dataclasses import dataclass
from pathlib import Path

from .actions import Reader, switch_to_dhcp, switch_to_profile
from .config import AppConfig, ConfigError, load_config
from .models import ProfileError
from .netsh import NetshError
from .shell import Runner, run_command
from .status import read_status

TASK_NAME = "IPSwitchHelper"
ACTIONS = {"dhcp", "profile"}


@dataclass(frozen=True)
class Request:
    id: str
    action: str
    profile: str | None = None


@dataclass(frozen=True)
class Result:
    id: str
    ok: bool
    message: str


def request_to_json(request: Request) -> str:
    return json.dumps({"id": request.id, "action": request.action, "profile": request.profile})


def request_from_json(text: str) -> Request:
    raw = json.loads(text)
    if not isinstance(raw, dict):
        raise ValueError("la solicitud no es un objeto JSON")
    request_id = raw.get("id")
    action = raw.get("action")
    profile = raw.get("profile")
    if not isinstance(request_id, str) or not request_id:
        raise ValueError("falta id")
    if action not in ACTIONS:
        raise ValueError(f"acción desconocida: {action}")
    if action == "profile" and not isinstance(profile, str):
        raise ValueError("falta el nombre de perfil")
    return Request(request_id, action, profile if action == "profile" else None)


def result_to_json(result: Result) -> str:
    return json.dumps({"id": result.id, "ok": result.ok, "message": result.message}, ensure_ascii=False)


def result_from_json(text: str) -> Result:
    raw = json.loads(text)
    try:
        return Result(str(raw["id"]), bool(raw["ok"]), str(raw["message"]))
    except (KeyError, TypeError) as exc:
        raise ValueError(f"resultado inválido: {exc}") from exc


def runtime_dir() -> Path:
    base = os.environ.get("LOCALAPPDATA") or str(Path.home())
    return Path(base) / "ipswitch"


def request_path(runtime: Path, request_id: str) -> Path:
    return runtime / f"request-{request_id}.json"


def result_path(runtime: Path, request_id: str) -> Path:
    return runtime / f"result-{request_id}.json"


def write_atomic(path: Path, text: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_name(path.name + ".tmp")
    tmp.write_text(text, encoding="utf-8")
    os.replace(tmp, path)


def handle_request(
    request: Request, config: AppConfig, runner: Runner = run_command, reader: Reader = read_status
) -> Result:
    try:
        if request.action == "dhcp":
            switch_to_dhcp(config.adapter, reader=reader, runner=runner)
            return Result(request.id, True, "DHCP activado")
        profile = next((p for p in config.profiles if p.name == request.profile), None)
        if profile is None:
            return Result(request.id, False, f"Perfil no encontrado: {request.profile}")
        switch_to_profile(config.adapter, profile, runner=runner)
        return Result(request.id, True, f"Perfil {profile.name} aplicado")
    except (NetshError, ProfileError) as exc:
        return Result(request.id, False, str(exc))


def _mtime(path: Path) -> float:
    try:
        return path.stat().st_mtime
    except OSError:
        return 0.0


def run_helper(
    runtime: Path, config_path: Path, runner: Runner = run_command, reader: Reader = read_status
) -> list[Result]:
    pending = sorted(runtime.glob("request-*.json"), key=_mtime)
    if not pending:
        return []
    config: AppConfig | None
    try:
        config = load_config(config_path)
        config_error = ""
    except ConfigError as exc:
        config = None
        config_error = str(exc)
    results = []
    for path in pending:
        request_id = path.stem.removeprefix("request-")
        try:
            request = request_from_json(path.read_text(encoding="utf-8"))
        except (OSError, ValueError) as exc:
            result = Result(request_id, False, f"Solicitud inválida: {exc}")
        else:
            if request.id != request_id:
                result = Result(request_id, False, "Solicitud inválida: id no coincide")
            elif config is None:
                result = Result(request_id, False, config_error)
            else:
                result = handle_request(request, config, runner=runner, reader=reader)
        write_atomic(result_path(runtime, request_id), result_to_json(result))
        try:
            path.unlink()
        except OSError:
            pass
        results.append(result)
    return results
