"""Instalación del helper elevado.

La tarea programada corre con privilegios máximos, así que todo lo que ejecuta debe estar en
carpetas que solo un administrador puede modificar:

- Una copia del intérprete (solo stdlib, sin site-packages) y del paquete en
  ``%ProgramFiles%\\ipswitch``. Un archivo ``pythonXY._pth`` fija ``sys.path`` y hace que Python
  ignore ``PYTHONPATH``/``PYTHONHOME`` y la carpeta actual.
- Config y resultados en ``%ProgramData%\\ipswitch``, con dueño Administradores.
"""

from __future__ import annotations

import ctypes
import shutil
import sys
from pathlib import Path

from .config import default_config_path, ensure_config
from .frozen import app_dir, dock_exe, is_frozen
from .helper import TASK_NAME
from .paths import FOLDERID_PROGRAM_FILES, known_folder
from .shell import Runner
from .status import powershell_args, ps_quote, utf8_runner

PACKAGE_DIR = Path(__file__).resolve().parent
ROOT_FILE_SUFFIXES = {".exe", ".dll"}
SKIPPED_LIB_DIRS = {"site-packages", "test", "idlelib", "tkinter", "turtledemo", "ensurepip", "venv", "__pycache__"}
ADMIN_ONLY_ACL = (
    "/inheritance:r /grant:r '*S-1-5-32-544:(OI)(CI)F' '*S-1-5-18:(OI)(CI)F' '*S-1-5-32-545:(OI)(CI)RX'"
)


class InstallError(RuntimeError):
    pass


def is_admin() -> bool:
    try:
        return bool(ctypes.windll.shell32.IsUserAnAdmin())
    except (AttributeError, OSError):
        return False


def install_dir() -> Path:
    return known_folder(FOLDERID_PROGRAM_FILES) / "ipswitch"


def _ignore_lib(directory: str, names: list[str]) -> set[str]:
    return {name for name in names if name in SKIPPED_LIB_DIRS}


def deploy_runtime(base_prefix: Path, package_dir: Path, target: Path) -> None:
    python = target / "python"
    app = target / "app"
    for old in (python, app):
        if old.exists():
            shutil.rmtree(old)
    python.mkdir(parents=True)
    for item in base_prefix.iterdir():
        if item.is_file() and item.suffix.lower() in ROOT_FILE_SUFFIXES:
            shutil.copy2(item, python / item.name)
    shutil.copytree(base_prefix / "DLLs", python / "DLLs")
    shutil.copytree(base_prefix / "Lib", python / "Lib", ignore=_ignore_lib)
    pth = python / f"python{sys.version_info.major}{sys.version_info.minor}._pth"
    pth.write_text("DLLs\nLib\n..\\app\n", encoding="utf-8")
    shutil.copytree(package_dir, app / package_dir.name, ignore=shutil.ignore_patterns("__pycache__"))


def helper_action(target: Path) -> tuple[str, str, str]:
    return str(target / "python" / "pythonw.exe"), "-I -m ipswitch helper", str(target / "app")


def helper_action_frozen(executable: str | Path) -> tuple[str, str, str]:
    """App instalada: la tarea corre IPDock.exe de Program Files (solo-admin), sin copiar Python."""
    return str(dock_exe(executable)), "helper", str(app_dir(executable))


def _secure_dir(variable: str) -> list[str]:
    return [
        f"New-Item -ItemType Directory -Force -Path {variable} | Out-Null",
        f"icacls {variable} /setowner '*S-1-5-32-544' /T /C | Out-Null",
        f'if ($LASTEXITCODE -ne 0) {{ throw "icacls /setowner falló ($LASTEXITCODE)" }}',
        f"icacls {variable} {ADMIN_ONLY_ACL} /T /C | Out-Null",
        f'if ($LASTEXITCODE -ne 0) {{ throw "icacls falló ($LASTEXITCODE)" }}',
    ]


def prepare_script(config_dir: str, target_dir: str) -> str:
    return "\n".join([
        "[Console]::OutputEncoding = [Text.Encoding]::UTF8",
        "$ProgressPreference = 'SilentlyContinue'",
        "$ErrorActionPreference = 'Stop'",
        f"$config = {ps_quote(config_dir)}",
        f"$target = {ps_quote(target_dir)}",
        # Un config.json creado antes por un usuario sin admin no es confiable: se aparta.
        "$cfg = Join-Path $config 'config.json'",
        "if (Test-Path -LiteralPath $cfg) {",
        "  $owner = (Get-Acl -LiteralPath $cfg).GetOwner([Security.Principal.SecurityIdentifier]).Value",
        "  if ($owner -notin @('S-1-5-32-544', 'S-1-5-18')) {",
        "    Move-Item -LiteralPath $cfg -Destination (Join-Path $config 'config.json.untrusted') -Force",
        "  }",
        "}",
        *_secure_dir("$config"),
        *_secure_dir("$target"),
    ])


def register_script(executable: str, arguments: str, workdir: str) -> str:
    return "\n".join([
        "[Console]::OutputEncoding = [Text.Encoding]::UTF8",
        "$ProgressPreference = 'SilentlyContinue'",
        "$ErrorActionPreference = 'Stop'",
        f"$action = New-ScheduledTaskAction -Execute {ps_quote(executable)} -Argument {ps_quote(arguments)}"
        f" -WorkingDirectory {ps_quote(workdir)}",
        "$user = [Security.Principal.WindowsIdentity]::GetCurrent().Name",
        "$principal = New-ScheduledTaskPrincipal -UserId $user -LogonType Interactive -RunLevel Highest",
        "$settings = New-ScheduledTaskSettingsSet -AllowStartIfOnBatteries -DontStopIfGoingOnBatteries"
        " -MultipleInstances Queue -ExecutionTimeLimit (New-TimeSpan -Minutes 2)",
        f"Register-ScheduledTask -TaskName {ps_quote(TASK_NAME)} -Action $action -Principal $principal"
        " -Settings $settings -Force | Out-Null",
    ])


def uninstall_script() -> str:
    return "\n".join([
        "[Console]::OutputEncoding = [Text.Encoding]::UTF8",
        "$ErrorActionPreference = 'Stop'",
        f"Unregister-ScheduledTask -TaskName {ps_quote(TASK_NAME)} -Confirm:$false",
    ])


def _run(runner: Runner, script: str, what: str) -> None:
    result = runner(powershell_args(script))
    if result.returncode != 0:
        raise InstallError(f"Falló {what}:\n{result.output}")


def install(
    config_path: Path | None = None,
    target: Path | None = None,
    base_prefix: Path | None = None,
    package_dir: Path = PACKAGE_DIR,
    runner: Runner = utf8_runner,
    frozen: bool | None = None,
    executable: str | None = None,
) -> list[str]:
    config_path = config_path or default_config_path()
    frozen = is_frozen() if frozen is None else frozen
    executable = executable or sys.executable
    target = target or (app_dir(executable) if frozen else install_dir())
    base_prefix = base_prefix or Path(sys.base_prefix)
    _run(runner, prepare_script(str(config_path.parent), str(target)), "la preparación de carpetas")
    warnings = []
    untrusted = config_path.with_name("config.json.untrusted")
    if untrusted.exists():
        warnings.append(
            f"Había un config.json que no creó un administrador; se movió a {untrusted}. "
            "Revisalo y copiá a mano los perfiles en los que confíes."
        )
    ensure_config(config_path)
    (config_path.parent / "results").mkdir(exist_ok=True)
    if frozen:
        action = helper_action_frozen(executable)
    else:
        deploy_runtime(base_prefix, package_dir, target)
        action = helper_action(target)
    _run(runner, register_script(*action), "el registro de la tarea")
    return warnings


def uninstall(runner: Runner = utf8_runner) -> None:
    _run(runner, uninstall_script(), "la desinstalación")
