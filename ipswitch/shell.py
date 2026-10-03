from __future__ import annotations

import subprocess
from dataclasses import dataclass
from typing import Callable, Sequence


@dataclass(frozen=True)
class CommandResult:
    returncode: int
    output: str


Runner = Callable[[Sequence[str]], CommandResult]


def run_command(args: Sequence[str], encoding: str = "oem") -> CommandResult:
    proc = subprocess.run(
        list(args),
        capture_output=True,
        creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0),
    )
    output = (proc.stdout + proc.stderr).decode(encoding, errors="replace").strip()
    return CommandResult(proc.returncode, output)
