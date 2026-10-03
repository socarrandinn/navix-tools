import base64
import json

import pytest

from ipswitch.shell import CommandResult
from ipswitch.status import (
    AdapterStatus,
    StatusError,
    describe,
    list_adapters,
    parse_status,
    powershell_args,
    ps_quote,
    read_status,
    status_script,
)


def decode(args):
    assert args[:4] == ["powershell", "-NoProfile", "-NonInteractive", "-EncodedCommand"]
    return base64.b64decode(args[4]).decode("utf-16-le")


def test_ps_quote():
    assert ps_quote("Wi-Fi") == "'Wi-Fi'"
    assert ps_quote("Bob's NIC") == "'Bob''s NIC'"


def test_status_script_escapes_single_quotes():
    script = status_script("Bob's NIC")
    assert "$a = 'Bob''s NIC'" in script
    assert "ConvertTo-Json" in script


def test_powershell_args_roundtrip_non_ascii():
    script = status_script("Conexión de área local* 1")
    assert decode(powershell_args(script)) == script


def test_parse_static_status():
    text = json.dumps({"dhcp": "Disabled", "ip": "192.168.0.100", "prefix": 24,
                       "gateway": "192.168.0.254", "dns": ["192.168.0.254", "8.8.8.8"]})
    assert parse_status(text) == AdapterStatus(False, "192.168.0.100", 24, "192.168.0.254",
                                               ("192.168.0.254", "8.8.8.8"))


def test_parse_disconnected_dhcp_status():
    text = json.dumps({"dhcp": "Enabled", "ip": None, "prefix": None, "gateway": None, "dns": []})
    assert parse_status(text) == AdapterStatus(True, None, None, None, ())


def test_parse_single_dns_as_string():
    text = json.dumps({"dhcp": "Enabled", "ip": "10.0.0.2", "prefix": 8, "gateway": "10.0.0.1",
                       "dns": "10.0.0.1"})
    assert parse_status(text).dns == ("10.0.0.1",)


def test_parse_garbage_raises():
    with pytest.raises(StatusError):
        parse_status("Get-NetIPInterface : No se encontró ...")


def test_read_status_uses_runner():
    seen = []

    def runner(args):
        seen.append(decode(list(args)))
        return CommandResult(0, json.dumps({"dhcp": "Enabled", "ip": "10.0.0.2", "prefix": 8,
                                            "gateway": "10.0.0.1", "dns": []}))

    status = read_status("Wi-Fi", runner=runner)
    assert status.dhcp is True
    assert "$a = 'Wi-Fi'" in seen[0]


def test_read_status_failure_raises_with_output():
    def runner(args):
        return CommandResult(1, "No MSFT_NetIPInterface objects found")

    with pytest.raises(StatusError, match="No MSFT_NetIPInterface"):
        read_status("Nope", runner=runner)


def test_list_adapters():
    def runner(args):
        assert "Get-NetAdapter" in decode(list(args))
        return CommandResult(0, '["Wi-Fi","vEthernet (WSL (Hyper-V firewall))"]')

    assert list_adapters(runner=runner) == ["Wi-Fi", "vEthernet (WSL (Hyper-V firewall))"]


def test_list_adapters_single_string():
    assert list_adapters(runner=lambda a: CommandResult(0, '"Wi-Fi"')) == ["Wi-Fi"]


def test_describe_static():
    status = AdapterStatus(False, "192.168.0.100", 24, "192.168.0.254", ("192.168.0.254", "8.8.8.8"))
    assert describe(status) == (
        "Modo:    IP fija\n"
        "IP:      192.168.0.100/24\n"
        "Gateway: 192.168.0.254\n"
        "DNS:     192.168.0.254, 8.8.8.8"
    )


def test_describe_dhcp_without_lease():
    assert describe(AdapterStatus(True, None, None, None, ())) == (
        "Modo:    DHCP\n"
        "IP:      —\n"
        "Gateway: —\n"
        "DNS:     —"
    )


def test_scripts_silence_progress_records():
    from ipswitch.status import ADAPTERS_SCRIPT

    assert "$ProgressPreference = 'SilentlyContinue'" in status_script("Wi-Fi")
    assert "$ProgressPreference = 'SilentlyContinue'" in ADAPTERS_SCRIPT


def test_utf8_runner_ignores_stderr_noise_on_success(monkeypatch):
    import subprocess

    from ipswitch import status as status_module

    def fake_run(args, capture_output, creationflags):
        return subprocess.CompletedProcess(args, 0, stdout='["Wi-Fi"]\r\n'.encode("utf-8"),
                                           stderr=b"#< CLIXML\r\n<Objs/>")

    monkeypatch.setattr(subprocess, "run", fake_run)
    assert status_module.utf8_runner(["powershell"]) == CommandResult(0, '["Wi-Fi"]')


def test_utf8_runner_keeps_stderr_on_failure(monkeypatch):
    import subprocess

    from ipswitch import status as status_module

    def fake_run(args, capture_output, creationflags):
        return subprocess.CompletedProcess(args, 1, stdout=b"", stderr="No se encontró".encode("utf-8"))

    monkeypatch.setattr(subprocess, "run", fake_run)
    assert status_module.utf8_runner(["powershell"]) == CommandResult(1, "No se encontró")
