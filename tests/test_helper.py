import pytest

from ipswitch.config import AppConfig, save_config
from ipswitch.helper import (
    Request,
    Result,
    handle_request,
    request_from_json,
    request_path,
    request_to_json,
    result_from_json,
    result_path,
    result_to_json,
    run_helper,
    runtime_dir,
    write_atomic,
)
from ipswitch.models import StaticProfile
from tests.fakes import FakeRunner, make_status

CASA = StaticProfile("Casa", "192.168.0.100", 24, "192.168.0.254", ("192.168.0.254",))
CONFIG = AppConfig("Wi-Fi", (CASA,))
STATIC = lambda adapter: make_status(False, "192.168.0.100", 24)  # noqa: E731


def test_request_and_result_roundtrip():
    request = Request("abc", "profile", "Casa")
    assert request_from_json(request_to_json(request)) == request
    assert request_from_json(request_to_json(Request("d", "dhcp"))) == Request("d", "dhcp", None)
    result = Result("abc", True, "ok")
    assert result_from_json(result_to_json(result)) == result


@pytest.mark.parametrize(
    "text",
    ["nope", "[]", '{"action": "dhcp"}', '{"id": "x", "action": "format_c"}', '{"id": "x", "action": "profile"}'],
)
def test_request_from_json_rejects_garbage(text):
    with pytest.raises(ValueError):
        request_from_json(text)


def test_result_from_json_rejects_garbage():
    with pytest.raises(ValueError):
        result_from_json('{"id": "x"}')


def test_runtime_dir_uses_localappdata(monkeypatch, tmp_path):
    monkeypatch.setenv("LOCALAPPDATA", str(tmp_path))
    assert runtime_dir() == tmp_path / "ipswitch"


def test_handle_dhcp():
    runner = FakeRunner()
    assert handle_request(Request("1", "dhcp"), CONFIG, runner=runner, reader=STATIC) == Result("1", True, "DHCP activado")
    assert runner.calls


def test_handle_profile():
    runner = FakeRunner()
    result = handle_request(Request("2", "profile", "Casa"), CONFIG, runner=runner, reader=STATIC)
    assert result == Result("2", True, "Perfil Casa aplicado")


def test_handle_unknown_profile_does_not_touch_network():
    runner = FakeRunner()
    result = handle_request(Request("3", "profile", "Oficina"), CONFIG, runner=runner, reader=STATIC)
    assert result.ok is False
    assert "no encontrado" in result.message
    assert runner.calls == []


def test_handle_netsh_failure_is_reported():
    runner = FakeRunner(fail_on="address=192.168.0.100")
    result = handle_request(Request("4", "profile", "Casa"), CONFIG, runner=runner, reader=STATIC)
    assert result.ok is False
    assert "Falló" in result.message


def test_run_helper_with_nothing_pending(tmp_path):
    assert run_helper(tmp_path, tmp_path / "config.json", runner=FakeRunner(), reader=STATIC) == []


def test_run_helper_processes_all_pending(tmp_path):
    config_path = tmp_path / "cfg" / "config.json"
    save_config(config_path, CONFIG)
    write_atomic(request_path(tmp_path, "a"), request_to_json(Request("a", "dhcp")))
    write_atomic(request_path(tmp_path, "b"), request_to_json(Request("b", "profile", "Casa")))
    results = run_helper(tmp_path, config_path, runner=FakeRunner(), reader=STATIC)
    assert sorted(r.id for r in results) == ["a", "b"]
    assert result_from_json(result_path(tmp_path, "a").read_text(encoding="utf-8")).ok
    assert result_from_json(result_path(tmp_path, "b").read_text(encoding="utf-8")).ok
    assert not request_path(tmp_path, "a").exists()
    assert not request_path(tmp_path, "b").exists()


def test_run_helper_invalid_request_writes_error(tmp_path):
    config_path = tmp_path / "config.json"
    save_config(config_path, CONFIG)
    request_path(tmp_path, "bad").write_text("{oops", encoding="utf-8")
    (result,) = run_helper(tmp_path, config_path, runner=FakeRunner(), reader=STATIC)
    assert result.id == "bad"
    assert result.ok is False
    assert "Solicitud inválida" in result.message


def test_run_helper_rejects_mismatched_id(tmp_path):
    config_path = tmp_path / "config.json"
    save_config(config_path, CONFIG)
    write_atomic(request_path(tmp_path, "x"), request_to_json(Request("y", "dhcp")))
    runner = FakeRunner()
    (result,) = run_helper(tmp_path, config_path, runner=runner, reader=STATIC)
    assert result == Result("x", False, "Solicitud inválida: id no coincide")
    assert runner.calls == []


def test_run_helper_missing_config_reports_install(tmp_path):
    write_atomic(request_path(tmp_path, "c"), request_to_json(Request("c", "dhcp")))
    (result,) = run_helper(tmp_path, tmp_path / "nope.json", runner=FakeRunner(), reader=STATIC)
    assert result.ok is False
    assert "install" in result.message
