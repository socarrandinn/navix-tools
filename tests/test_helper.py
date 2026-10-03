import _winapi
import os
import time

import pytest

from ipswitch.config import AppConfig, save_config
from ipswitch.helper import (
    Request,
    Result,
    handle_request,
    is_reparse_point,
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


@pytest.fixture
def dirs(tmp_path):
    requests = tmp_path / "user" / "ipswitch"
    results = tmp_path / "admin" / "results"
    config_path = tmp_path / "admin" / "config.json"
    requests.mkdir(parents=True)
    save_config(config_path, CONFIG)
    return requests, results, config_path


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


def test_runtime_dir_is_under_local_app_data():
    assert runtime_dir().name == "ipswitch"
    assert runtime_dir().parent.name.lower() == "local"


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


def test_handle_unexpected_error_becomes_failed_result():
    def runner(args):
        raise OSError("netsh no encontrado")

    result = handle_request(Request("5", "profile", "Casa"), CONFIG, runner=runner, reader=STATIC)
    assert result.ok is False
    assert "Error inesperado" in result.message
    assert "netsh no encontrado" in result.message


def test_run_helper_with_nothing_pending(dirs):
    requests, results, config_path = dirs
    assert run_helper(requests, results, config_path, runner=FakeRunner(), reader=STATIC) == []


def test_run_helper_processes_all_pending_into_results_dir(dirs):
    requests, results, config_path = dirs
    write_atomic(request_path(requests, "a"), request_to_json(Request("a", "dhcp")))
    write_atomic(request_path(requests, "b"), request_to_json(Request("b", "profile", "Casa")))
    out = run_helper(requests, results, config_path, runner=FakeRunner(), reader=STATIC)
    assert sorted(r.id for r in out) == ["a", "b"]
    assert result_from_json(result_path(results, "a").read_text(encoding="utf-8")).ok
    assert result_from_json(result_path(results, "b").read_text(encoding="utf-8")).ok
    assert not request_path(requests, "a").exists()
    assert not request_path(requests, "b").exists()
    assert list(requests.glob("result-*")) == []


def test_run_helper_continues_after_unexpected_error(dirs):
    requests, results, config_path = dirs
    calls = []

    def runner(args):
        calls.append(list(args))
        if len(calls) == 1:
            raise OSError("fallo raro")
        return FakeRunner()(args)

    write_atomic(request_path(requests, "a"), request_to_json(Request("a", "profile", "Casa")))
    write_atomic(request_path(requests, "b"), request_to_json(Request("b", "profile", "Casa")))
    out = run_helper(requests, results, config_path, runner=runner, reader=STATIC)
    assert len(out) == 2
    assert [r.ok for r in out].count(False) == 1
    assert list(requests.glob("request-*.json")) == []


def test_run_helper_invalid_request_writes_error(dirs):
    requests, results, config_path = dirs
    request_path(requests, "bad").write_text("{oops", encoding="utf-8")
    (result,) = run_helper(requests, results, config_path, runner=FakeRunner(), reader=STATIC)
    assert result.id == "bad"
    assert result.ok is False
    assert "Solicitud inválida" in result.message


def test_run_helper_rejects_mismatched_id(dirs):
    requests, results, config_path = dirs
    write_atomic(request_path(requests, "x"), request_to_json(Request("y", "dhcp")))
    runner = FakeRunner()
    (result,) = run_helper(requests, results, config_path, runner=runner, reader=STATIC)
    assert result == Result("x", False, "Solicitud inválida: id no coincide")
    assert runner.calls == []


def test_run_helper_missing_config_reports_install(dirs, tmp_path):
    requests, results, _ = dirs
    write_atomic(request_path(requests, "c"), request_to_json(Request("c", "dhcp")))
    (result,) = run_helper(requests, results, tmp_path / "nope.json", runner=FakeRunner(), reader=STATIC)
    assert result.ok is False
    assert "install" in result.message


def test_run_helper_refuses_junctioned_requests_dir(tmp_path):
    target = tmp_path / "target"
    target.mkdir()
    (target / "keep.txt").write_text("no tocar", encoding="utf-8")
    write_atomic(request_path(target, "j"), request_to_json(Request("j", "dhcp")))
    junction = tmp_path / "junction"
    _winapi.CreateJunction(str(target), str(junction))
    assert is_reparse_point(junction)
    config_path = tmp_path / "config.json"
    save_config(config_path, CONFIG)
    runner = FakeRunner()
    assert run_helper(junction, tmp_path / "results", config_path, runner=runner, reader=STATIC) == []
    assert runner.calls == []
    assert request_path(target, "j").exists()


def test_run_helper_skips_junctioned_request_file(dirs, tmp_path):
    requests, results, config_path = dirs
    elsewhere = tmp_path / "elsewhere"
    elsewhere.mkdir()
    _winapi.CreateJunction(str(elsewhere), str(requests / "request-evil.json"))
    runner = FakeRunner()
    assert run_helper(requests, results, config_path, runner=runner, reader=STATIC) == []
    assert elsewhere.exists()
    assert runner.calls == []


def test_run_helper_sweeps_old_results(dirs):
    requests, results, config_path = dirs
    results.mkdir(parents=True)
    old = result_path(results, "old")
    fresh = result_path(results, "fresh")
    old.write_text(result_to_json(Result("old", True, "viejo")), encoding="utf-8")
    fresh.write_text(result_to_json(Result("fresh", True, "nuevo")), encoding="utf-8")
    past = time.time() - 3600
    os.utime(old, (past, past))
    run_helper(requests, results, config_path, runner=FakeRunner(), reader=STATIC)
    assert not old.exists()
    assert fresh.exists()
