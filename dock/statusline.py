"""Registrador de uso de Claude vía la status line de Claude Code.

Claude Code ejecuta el comando de ``statusLine`` en cada actualización y le pasa por stdin un JSON
con ``rate_limits`` (planes Pro/Max). Este comando guarda ese dato para la app "Uso de IA" y luego
ejecuta la status line que el usuario tenía antes, con la misma entrada, para no perderla.

    python -m dock.statusline install     # encadena la status line actual y registra el uso
    python -m dock.statusline uninstall   # restaura la status line anterior
"""

from __future__ import annotations

import json
import os
import shutil
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Callable

from .usage import record_claude

ROOT = Path(__file__).resolve().parent.parent
ChainRunner = Callable[[str, str], str]


def data_dir() -> Path:
    return Path(os.environ.get("LOCALAPPDATA") or Path.home()) / "ipdock"


def usage_path() -> Path:
    return data_dir() / "claude_usage.json"


def chain_path() -> Path:
    return data_dir() / "statusline_chain.json"


def settings_path() -> Path:
    return Path.home() / ".claude" / "settings.json"


def recorder_command(executable: str, script: str) -> str:
    return f'"{executable}" "{script}"'


def run_chained(command: str, stdin_text: str) -> str:
    proc = subprocess.run(
        command, shell=True, input=stdin_text.encode("utf-8"), capture_output=True, timeout=5,
        creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0),
    )
    return proc.stdout.decode("utf-8", errors="replace").rstrip("\r\n")


def run(stdin_text: str, usage: Path, chain: Path, now: datetime, runner: ChainRunner = run_chained) -> str:
    record_claude(stdin_text, usage, now)
    try:
        previous = json.loads(chain.read_text(encoding="utf-8"))
        command = previous["command"]
    except (OSError, ValueError, KeyError, TypeError):
        return ""
    try:
        return runner(command, stdin_text)
    except (OSError, subprocess.SubprocessError):
        return ""


def _read_settings(settings: Path) -> dict:
    if not settings.exists():
        return {}
    return json.loads(settings.read_text(encoding="utf-8"))


def _write_settings(settings: Path, data: dict) -> None:
    settings.parent.mkdir(parents=True, exist_ok=True)
    settings.write_text(json.dumps(data, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")


def install(settings: Path, chain: Path, command: str) -> str:
    data = _read_settings(settings)
    current = data.get("statusLine")
    if isinstance(current, dict) and current.get("command") == command:
        return "La status line de IPDock ya estaba instalada."
    if settings.exists():
        shutil.copy2(settings, settings.with_name(settings.name + ".ipdock.bak"))
    chain.parent.mkdir(parents=True, exist_ok=True)
    chain.write_text(json.dumps(current), encoding="utf-8")
    data["statusLine"] = {"type": "command", "command": command}
    _write_settings(settings, data)
    return f"Instalado. Status line anterior encadenada: {current.get('command') if isinstance(current, dict) else 'ninguna'}"


def uninstall(settings: Path, chain: Path) -> str:
    data = _read_settings(settings)
    try:
        previous = json.loads(chain.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return "No había status line de IPDock instalada."
    if previous is None:
        data.pop("statusLine", None)
    else:
        data["statusLine"] = previous
    _write_settings(settings, data)
    chain.unlink(missing_ok=True)
    return "Status line anterior restaurada."


def main(argv: list[str] | None = None) -> int:
    argv = sys.argv[1:] if argv is None else argv
    if argv[:1] == ["install"]:
        script = ROOT / "ipdock_statusline.py"
        print(install(settings_path(), chain_path(), recorder_command(sys.executable, str(script))))
        return 0
    if argv[:1] == ["uninstall"]:
        print(uninstall(settings_path(), chain_path()))
        return 0
    stdin_text = sys.stdin.buffer.read().decode("utf-8", errors="replace")
    output = run(stdin_text, usage_path(), chain_path(), datetime.now(timezone.utc))
    if output:
        sys.stdout.buffer.write(output.encode("utf-8"))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
