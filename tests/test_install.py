import base64
from pathlib import Path

from ipswitch.config import DEFAULT_CONFIG, load_config
from ipswitch.install import (
    deploy_runtime,
    helper_action,
    install,
    prepare_script,
    register_script,
    uninstall,
    uninstall_script,
)
from ipswitch.shell import CommandResult
from tests.fakes import FakeRunner


def decode(args):
    return base64.b64decode(args[4]).decode("utf-16-le")


def make_base_python(root: Path) -> Path:
    base = root / "Python313"
    for name in ("python.exe", "pythonw.exe", "python313.dll", "python3.dll", "vcruntime140.dll", "LICENSE.txt"):
        (base / name).parent.mkdir(parents=True, exist_ok=True)
        (base / name).write_text(name)
    for rel in ("DLLs/_socket.pyd", "Lib/os.py", "Lib/json/__init__.py", "Lib/site-packages/evil.py",
                "Lib/test/test_x.py", "Lib/__pycache__/os.cpython-313.pyc", "Scripts/pip.exe", "tcl/x.tcl"):
        path = base / rel
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(rel)
    return base


def make_package(root: Path) -> Path:
    package = root / "src" / "ipswitch"
    package.mkdir(parents=True)
    (package / "__init__.py").write_text("")
    (package / "helper.py").write_text("# helper")
    (package / "__pycache__").mkdir()
    (package / "__pycache__" / "helper.cpython-313.pyc").write_text("x")
    return package


def test_deploy_runtime_copies_isolated_python_and_package(tmp_path):
    base = make_base_python(tmp_path)
    package = make_package(tmp_path)
    target = tmp_path / "Program Files" / "ipswitch"
    deploy_runtime(base, package, target)
    python = target / "python"
    for name in ("python.exe", "pythonw.exe", "python313.dll", "python3.dll", "vcruntime140.dll"):
        assert (python / name).exists(), name
    assert (python / "DLLs" / "_socket.pyd").exists()
    assert (python / "Lib" / "os.py").exists()
    assert (python / "Lib" / "json" / "__init__.py").exists()
    assert not (python / "Lib" / "site-packages").exists()
    assert not (python / "Lib" / "test").exists()
    assert not (python / "Lib" / "__pycache__").exists()
    assert not (python / "Scripts").exists()
    assert (python / "python313._pth").read_text(encoding="utf-8").splitlines() == ["DLLs", "Lib", r"..\app"]
    assert (target / "app" / "ipswitch" / "helper.py").read_text() == "# helper"
    assert not (target / "app" / "ipswitch" / "__pycache__").exists()


def test_deploy_runtime_replaces_previous_copy(tmp_path):
    base = make_base_python(tmp_path)
    package = make_package(tmp_path)
    target = tmp_path / "Program Files" / "ipswitch"
    stale = target / "app" / "ipswitch" / "stale.py"
    stale.parent.mkdir(parents=True)
    stale.write_text("viejo")
    deploy_runtime(base, package, target)
    assert not stale.exists()


def test_helper_action_runs_isolated_copy(tmp_path):
    target = tmp_path / "Program Files" / "ipswitch"
    assert helper_action(target) == (
        str(target / "python" / "pythonw.exe"), "-I -m ipswitch helper", str(target / "app"))


def test_prepare_script_contents():
    script = prepare_script(r"C:\ProgramData\ipswitch", r"C:\Program Files\ipswitch")
    for fragment in [
        "$ProgressPreference = 'SilentlyContinue'",
        "[Console]::OutputEncoding = [Text.Encoding]::UTF8",
        "'C:\\ProgramData\\ipswitch'",
        "'C:\\Program Files\\ipswitch'",
        "New-Item -ItemType Directory -Force",
        "GetOwner([Security.Principal.SecurityIdentifier])",
        "config.json.untrusted",
        "/setowner '*S-1-5-32-544' /T /C",
        "/inheritance:r",
        "'*S-1-5-32-544:(OI)(CI)F'",
        "'*S-1-5-18:(OI)(CI)F'",
        "'*S-1-5-32-545:(OI)(CI)RX'",
    ]:
        assert fragment in script, fragment


def test_prepare_script_lets_files_inherit_the_acl():
    # (OI)(CI) con /T deja a los archivos con la DACL vacía: ni los usuarios pueden ejecutar NavixTools.exe.
    script = prepare_script(r"C:\ProgramData\ipswitch", r"C:\Program Files\ipswitch")
    grants = [line for line in script.splitlines() if "/inheritance:r" in line]
    assert grants and all("/T" not in line for line in grants)
    assert "icacls (Join-Path $config '*') /reset /T /C" in script
    assert "icacls (Join-Path $target '*') /reset /T /C" in script


def test_register_script_contents():
    script = register_script(r"C:\Program Files\ipswitch\python\pythonw.exe", "-I -m ipswitch helper",
                             r"C:\Program Files\ipswitch\app")
    for fragment in [
        "-Execute 'C:\\Program Files\\ipswitch\\python\\pythonw.exe'",
        "-Argument '-I -m ipswitch helper'",
        "-WorkingDirectory 'C:\\Program Files\\ipswitch\\app'",
        "-RunLevel Highest",
        "-AllowStartIfOnBatteries",
        "-DontStopIfGoingOnBatteries",
        "-MultipleInstances Queue",
        "-TaskName 'IPSwitchHelper'",
        "-Force",
    ]:
        assert fragment in script, fragment


def test_scripts_quote_paths():
    script = register_script(r"C:\Bob's\pythonw.exe", "-I -m ipswitch helper", r"E:\Bob's")
    assert "-Execute 'C:\\Bob''s\\pythonw.exe'" in script
    assert "-WorkingDirectory 'E:\\Bob''s'" in script
    assert "'C:\\Bob''s'" in prepare_script(r"C:\Bob's", r"C:\x")


def test_uninstall_script():
    assert "Unregister-ScheduledTask -TaskName 'IPSwitchHelper' -Confirm:$false" in uninstall_script()


def test_install_prepares_before_writing_config_then_deploys_and_registers(tmp_path):
    config_path = tmp_path / "ProgramData" / "ipswitch" / "config.json"
    target = tmp_path / "Program Files" / "ipswitch"
    base = make_base_python(tmp_path)
    package = make_package(tmp_path)
    seen = []

    def runner(args):
        script = decode(list(args))
        seen.append((script, config_path.exists(), (target / "python" / "pythonw.exe").exists()))
        return CommandResult(0, "")

    warnings = install(config_path=config_path, target=target, base_prefix=base, package_dir=package, runner=runner)
    assert warnings == []
    (prepare, config_before, _), (register, config_after, deployed) = seen
    assert "/setowner" in prepare and config_before is False
    assert "Register-ScheduledTask" in register and config_after is True and deployed is True
    assert load_config(config_path) == DEFAULT_CONFIG
    assert (config_path.parent / "results").is_dir()


def test_install_warns_when_untrusted_config_was_quarantined(tmp_path):
    config_path = tmp_path / "ProgramData" / "ipswitch" / "config.json"

    def runner(args):
        if "/setowner" in decode(list(args)):
            config_path.parent.mkdir(parents=True, exist_ok=True)
            config_path.with_name("config.json.untrusted").write_text("{}", encoding="utf-8")
        return CommandResult(0, "")

    warnings = install(config_path=config_path, target=tmp_path / "pf", base_prefix=make_base_python(tmp_path),
                       package_dir=make_package(tmp_path), runner=runner)
    assert len(warnings) == 1
    assert "config.json.untrusted" in warnings[0]


def test_uninstall_runs_script():
    runner = FakeRunner()
    uninstall(runner=runner)
    assert "Unregister-ScheduledTask" in decode(runner.calls[0])
