from __future__ import annotations

import json
import os
import stat
import time
from dataclasses import dataclass
from pathlib import Path

from .actions import Reader, switch_to_dhcp, switch_to_profile
from .config import AppConfig, ConfigError, default_config_path, load_config
from .models import ProfileError
from .netsh import NetshError
from .paths import FOLDERID_LOCAL_APP_DATA, known_folder
from .shell import Runner, run_command
from .status import read_status

TASK_NAME = "IPSwitchHelper"
ACTIONS = {"dhcp", "profile"}
RESULT_MAX_AGE_S = 600


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
    """Carpeta del usuario donde el cliente deja solicitudes (escribible sin admin)."""
    return known_folder(FOLDERID_LOCAL_APP_DATA) / "ipswitch"


def results_dir() -> Path:
    """Carpeta solo-admin donde el helper escribe resultados (los usuarios solo leen)."""
    return default_config_path().parent / "results"


def request_path(runtime: Path, request_id: str) -> Path:
    return runtime / f"request-{request_id}.json"


def result_path(results: Path, request_id: str) -> Path:
    return results / f"result-{request_id}.json"


def write_atomic(path: Path, text: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_name(path.name + ".tmp")
    tmp.write_text(text, encoding="utf-8")
    os.replace(tmp, path)


def is_reparse_point(path: Path) -> bool:
    try:
        return bool(os.lstat(path).st_file_attributes & stat.FILE_ATTRIBUTE_REPARSE_POINT)
    except OSError:
        return False


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
    except Exception as exc:  # noqa: BLE001 - un fallo no debe frenar las demás solicitudes
        return Result(request.id, False, f"Error inesperado: {type(exc).__name__}: {exc}")


def _mtime(path: Path) -> float:
    try:
        return path.stat().st_mtime
    except OSError:
        return 0.0


def _sweep_results(results: Path, now: float) -> None:
    for path in results.glob("result-*.json"):
        if now - _mtime(path) > RESULT_MAX_AGE_S:
            try:
                path.unlink()
            except OSError:
                pass


def run_helper(
    requests: Path,
    results: Path,
    config_path: Path,
    runner: Runner = run_command,
    reader: Reader = read_status,
    now=time.time,
) -> list[Result]:
    # requests es escribible por el usuario: nunca seguir junctions/symlinks como admin.
    if is_reparse_point(requests) or not requests.is_dir():
        return []
    results.mkdir(parents=True, exist_ok=True)
    _sweep_results(results, now())
    pending = sorted(
        (p for p in requests.glob("request-*.json") if not is_reparse_point(p) and p.is_file()),
        key=_mtime,
    )
    if not pending:
        return []
    config: AppConfig | None
    try:
        config = load_config(config_path)
        config_error = ""
    except ConfigError as exc:
        config = None
        config_error = str(exc)
    out = []
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
        write_atomic(result_path(results, request_id), result_to_json(result))
        try:
            path.unlink()
        except OSError:
            pass
        out.append(result)
    return out
