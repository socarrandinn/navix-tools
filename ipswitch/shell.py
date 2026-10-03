from __future__ import annotations

import subprocess
from dataclasses import dataclass
from typing import Callable, Sequence


@dataclass(frozen=True)
class CommandResult:
    returncode: int
    output: str


Runner = Callable[[Sequence[str]], CommandResult]


def run_command(args: Sequence[str], encoding: str = "oem", stdout_only_on_success: bool = False) -> CommandResult:
    proc = subprocess.run(
        list(args),
        capture_output=True,
        creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0),
    )
    raw = proc.stdout if proc.returncode == 0 and stdout_only_on_success else proc.stdout + proc.stderr
    return CommandResult(proc.returncode, raw.decode(encoding, errors="replace").strip())
