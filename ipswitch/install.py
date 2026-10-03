from __future__ import annotations

import ctypes
import sys
from pathlib import Path

from .config import default_config_path, ensure_config
from .helper import TASK_NAME
from .shell import Runner
from .status import powershell_args, ps_quote, utf8_runner

PACKAGE_ROOT = str(Path(__file__).resolve().parent.parent)


class InstallError(RuntimeError):
    pass


def is_admin() -> bool:
    try:
        return bool(ctypes.windll.shell32.IsUserAnAdmin())
    except (AttributeError, OSError):
        return False


def helper_launch(frozen: bool, executable: str, package_root: str) -> tuple[str, str, str]:
    if frozen:
        return executable, "helper", str(Path(executable).parent)
    pythonw = Path(executable).with_name("pythonw.exe")
    exe = str(pythonw) if pythonw.exists() else executable
    return exe, "-m ipswitch helper", package_root


def install_script(executable: str, arguments: str, workdir: str, config_dir: str) -> str:
    return "\n".join([
        "$ErrorActionPreference = 'Stop'",
        f"$dir = {ps_quote(config_dir)}",
        "icacls $dir /inheritance:r /grant:r '*S-1-5-32-544:(OI)(CI)F' '*S-1-5-18:(OI)(CI)F'"
        " '*S-1-5-32-545:(OI)(CI)RX' | Out-Null",
        'if ($LASTEXITCODE -ne 0) { throw "icacls falló ($LASTEXITCODE)" }',
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
        "$ErrorActionPreference = 'Stop'",
        f"Unregister-ScheduledTask -TaskName {ps_quote(TASK_NAME)} -Confirm:$false",
    ])


def install(config_path: Path | None = None, runner: Runner = utf8_runner) -> None:
    config_path = config_path or default_config_path()
    ensure_config(config_path)
    exe, arguments, workdir = helper_launch(getattr(sys, "frozen", False), sys.executable, PACKAGE_ROOT)
    result = runner(powershell_args(install_script(exe, arguments, workdir, str(config_path.parent))))
    if result.returncode != 0:
        raise InstallError(f"Falló la instalación:\n{result.output}")


def uninstall(runner: Runner = utf8_runner) -> None:
    result = runner(powershell_args(uninstall_script()))
    if result.returncode != 0:
        raise InstallError(f"Falló la desinstalación:\n{result.output}")
