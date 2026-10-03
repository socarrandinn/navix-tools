import base64

from ipswitch.config import DEFAULT_CONFIG, load_config
from ipswitch.install import helper_launch, install, install_script, uninstall, uninstall_script
from tests.fakes import FakeRunner


def decode(args):
    return base64.b64decode(args[4]).decode("utf-16-le")


def test_helper_launch_frozen():
    assert helper_launch(True, r"C:\Apps\IPDock\IPDock.exe", r"C:\ignored") == (
        r"C:\Apps\IPDock\IPDock.exe", "helper", r"C:\Apps\IPDock")


def test_helper_launch_source_prefers_pythonw(tmp_path):
    (tmp_path / "python.exe").write_text("")
    (tmp_path / "pythonw.exe").write_text("")
    assert helper_launch(False, str(tmp_path / "python.exe"), r"E:\proj") == (
        str(tmp_path / "pythonw.exe"), "-m ipswitch helper", r"E:\proj")


def test_helper_launch_source_without_pythonw(tmp_path):
    (tmp_path / "python.exe").write_text("")
    exe, _, _ = helper_launch(False, str(tmp_path / "python.exe"), r"E:\proj")
    assert exe == str(tmp_path / "python.exe")


def test_install_script_contents():
    script = install_script(r"C:\Py\pythonw.exe", "-m ipswitch helper", r"E:\proj", r"C:\ProgramData\ipswitch")
    for fragment in [
        "$dir = 'C:\\ProgramData\\ipswitch'",
        "/inheritance:r",
        "'*S-1-5-32-544:(OI)(CI)F'",
        "'*S-1-5-18:(OI)(CI)F'",
        "'*S-1-5-32-545:(OI)(CI)RX'",
        "-Execute 'C:\\Py\\pythonw.exe'",
        "-Argument '-m ipswitch helper'",
        "-WorkingDirectory 'E:\\proj'",
        "-RunLevel Highest",
        "-AllowStartIfOnBatteries",
        "-DontStopIfGoingOnBatteries",
        "-MultipleInstances Queue",
        "-TaskName 'IPSwitchHelper'",
        "-Force",
    ]:
        assert fragment in script, fragment


def test_install_script_quotes_paths():
    script = install_script(r"C:\Bob's\pythonw.exe", "-m ipswitch helper", r"E:\Bob's", r"C:\ProgramData\ipswitch")
    assert "-Execute 'C:\\Bob''s\\pythonw.exe'" in script
    assert "-WorkingDirectory 'E:\\Bob''s'" in script


def test_uninstall_script():
    script = uninstall_script()
    assert "Unregister-ScheduledTask -TaskName 'IPSwitchHelper' -Confirm:$false" in script


def test_install_creates_config_and_runs_script(tmp_path):
    config_path = tmp_path / "ipswitch" / "config.json"
    runner = FakeRunner()
    install(config_path=config_path, runner=runner)
    assert load_config(config_path) == DEFAULT_CONFIG
    (call,) = runner.calls
    assert "Register-ScheduledTask" in decode(call)
    assert str(tmp_path / "ipswitch") in decode(call)


def test_uninstall_runs_script():
    runner = FakeRunner()
    uninstall(runner=runner)
    assert "Unregister-ScheduledTask" in decode(runner.calls[0])
