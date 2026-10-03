from __future__ import annotations

import time
import uuid
from pathlib import Path

from .helper import (
    ACTIONS,
    TASK_NAME,
    Request,
    Result,
    request_path,
    request_to_json,
    result_from_json,
    result_path,
    runtime_dir,
    write_atomic,
)
from .shell import Runner, run_command


class HelperError(RuntimeError):
    pass


def request_switch(
    action: str,
    profile: str | None = None,
    *,
    runtime: Path | None = None,
    runner: Runner = run_command,
    timeout: float = 20.0,
    poll: float = 0.2,
    clock=time.monotonic,
    sleep=time.sleep,
) -> Result:
    if action not in ACTIONS:
        raise ValueError(f"Acción desconocida: {action}")
    runtime = runtime or runtime_dir()
    request = Request(uuid.uuid4().hex, action, profile)
    pending = request_path(runtime, request.id)
    write_atomic(pending, request_to_json(request))
    started = runner(["schtasks", "/Run", "/TN", TASK_NAME])
    if started.returncode != 0:
        pending.unlink(missing_ok=True)
        raise HelperError(
            "No se pudo iniciar el helper. ¿Está instalado? En una terminal de administrador ejecuta:\n"
            f"python -m ipswitch install\n\n{started.output}"
        )
    target = result_path(runtime, request.id)
    deadline = clock() + timeout
    while True:
        try:
            result = result_from_json(target.read_text(encoding="utf-8"))
        except (OSError, ValueError):
            result = None
        if result is not None:
            target.unlink(missing_ok=True)
            return result
        if clock() >= deadline:
            pending.unlink(missing_ok=True)
            raise HelperError(f"El helper no respondió a tiempo ({timeout:.0f} s)")
        sleep(poll)
