import pytest

from ipswitch.client import HelperError, request_switch
from ipswitch.config import AppConfig, save_config
from ipswitch.helper import Result, result_path, result_to_json, run_helper, write_atomic
from ipswitch.models import StaticProfile
from ipswitch.shell import CommandResult
from tests.fakes import FakeRunner, make_status

CASA = StaticProfile("Casa", "192.168.0.100", 24, "192.168.0.254", ())
NO_SLEEP = lambda seconds: None  # noqa: E731


def fake_clock(*values):
    it = iter(values)
    return lambda: next(it)


@pytest.fixture
def dirs(tmp_path):
    return tmp_path / "user", tmp_path / "admin" / "results"


def test_request_switch_returns_helper_result(dirs, tmp_path):
    requests, results = dirs
    config_path = tmp_path / "admin" / "config.json"
    save_config(config_path, AppConfig("Wi-Fi", (CASA,)))
    netsh = FakeRunner()

    def runner(args):
        assert list(args) == ["schtasks", "/Run", "/TN", "IPSwitchHelper"]
        run_helper(requests, results, config_path, runner=netsh, reader=lambda a: make_status(False))
        return CommandResult(0, "")

    result = request_switch("profile", "Casa", runtime=requests, results=results, runner=runner, sleep=NO_SLEEP)
    assert result.ok is True
    assert result.message == "Perfil Casa aplicado"
    assert netsh.calls
    assert list(requests.glob("request-*.json")) == []


def test_request_switch_task_missing_mentions_install(dirs):
    requests, results = dirs

    def runner(args):
        return CommandResult(1, "ERROR: El sistema no puede encontrar el archivo especificado.")

    with pytest.raises(HelperError, match="install"):
        request_switch("dhcp", runtime=requests, results=results, runner=runner, sleep=NO_SLEEP)
    assert list(requests.glob("request-*.json")) == []


def test_request_switch_times_out_cleans_request_and_mentions_install(dirs):
    requests, results = dirs
    with pytest.raises(HelperError) as info:
        request_switch(
            "dhcp", runtime=requests, results=results, runner=lambda a: CommandResult(0, ""),
            clock=fake_clock(0.0, 5.0, 25.0), sleep=NO_SLEEP,
        )
    assert "no respondió" in str(info.value)
    assert "install" in str(info.value)
    assert list(requests.glob("request-*.json")) == []


def test_request_switch_ignores_other_results(dirs):
    requests, results = dirs
    write_atomic(result_path(results, "old"), result_to_json(Result("old", True, "viejo")))
    with pytest.raises(HelperError, match="no respondió"):
        request_switch(
            "dhcp", runtime=requests, results=results, runner=lambda a: CommandResult(0, ""),
            clock=fake_clock(0.0, 25.0), sleep=NO_SLEEP,
        )
    assert result_path(results, "old").exists()


def test_request_switch_rejects_unknown_action(dirs):
    requests, results = dirs
    with pytest.raises(ValueError):
        request_switch("format_c", runtime=requests, results=results, runner=FakeRunner())
